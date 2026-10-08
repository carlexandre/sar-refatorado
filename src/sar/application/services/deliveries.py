from dataclasses import asdict
from datetime import date
import json
import uuid
from sar.domain.errors import DeliveryUncertain, SarError, ValidationError
from sar.domain.models import ExecutionResult, Notification
from sar.domain.periods import due_date, reference


class Deliveries:
    def __init__(self, repo, reports, invoices, history, notifications, identities, policy, mail_to="svc.popce@rnp.br"):
        self.repo, self.reports, self.invoices, self.history = repo, reports, invoices, history
        self.notifications, self.identities, self.policy = notifications, identities, policy
        self.mail_to = mail_to

    def run(self, identity, request, *, occurrence=None, schedule_id=None):
        self.policy.require(identity, "deliveries.send")
        if not request.include_invoice:
            raise ValidationError("Envio exige fatura e relatório juntos; recrie o agendamento com fatura.")
        if request.group_id and request.link_ids:
            raise ValidationError("Selecione grupo ou instituições, não ambos.")
        today = request.today or date.today()
        period, competence = reference(today, request.start, request.end)
        due = due_date(today, request.invoice_due_day)
        if request.group_id:
            group = self.repo.group(request.group_id)
            ids = self.repo.group_links(group.id)
            self.policy.require(identity, "deliveries.send", ids, [group.id])
            targets = [(group.id, group.nome, self.mail_to, ids, True, group.email_contato)]
        else:
            links = self.repo.institutions()
            if request.link_ids:
                requested = set(request.link_ids)
                if not requested <= {link.id for link in links}:
                    raise ValidationError("Instituição solicitada não encontrada.")
                links = [link for link in links if link.id in requested]
            else:
                links = [link for link in links if self.repo.profile(link.id)]
            self.policy.require(identity, "deliveries.send", [link.id for link in links])
            targets = [
                (link.id, link.nome_instituicao, self.mail_to, [link.id], False, link.email_contato) for link in links
            ]
        execution_id = uuid.uuid4().hex
        if not self.repo.start_execution(
            execution_id, occurrence or f"manual:{execution_id}", identity.subject, schedule_id
        ):
            return ExecutionResult("", "duplicate")
        result = ExecutionResult(execution_id, "running")
        try:
            for target_id, name, destination, ids, group_mode, contact in targets:
                try:
                    report_name = f"Relatorio_{'Grupo' if group_mode else 'Tecnico'}_{name.replace(' ', '_')}_{period.start:%m-%Y}.pdf"
                    report = self.reports.generate(
                        identity,
                        ids,
                        period,
                        manual=False,
                        filename=report_name,
                        history_period=competence,
                        partial=group_mode,
                    )
                except Exception:
                    result.errors.append(f"target:{target_id}:report_unavailable")
                    continue
                if report.skipped_ids:
                    result.errors.append(f"target:{target_id}:partial_report")
                artifacts = [report.artifact.id]
                result.artifacts.extend(artifacts)
                try:
                    invoice_name = f"Fatura_{'Grupo' if group_mode else 'Gigafor'}_{name.replace(' ', '_')}_{period.start:%m-%Y}.pdf"
                    invoice = self.invoices.issue(
                        identity,
                        target_id,
                        today,
                        due,
                        competence,
                        f"execution:{execution_id}:{'group' if group_mode else 'link'}:{target_id}",
                        group=group_mode,
                        execution_id=execution_id,
                        filename=invoice_name,
                    )
                    artifacts.append(invoice.id)
                    result.artifacts.append(invoice.id)
                except Exception:
                    result.errors.append(f"target:{target_id}:invoice_unavailable")
                    continue
                if not destination:
                    result.errors.append(f"target:{target_id}:no_recipient")
                    continue
                subject, body = self._message(name, period, due)
                message_id = uuid.uuid4().hex
                self.repo.enqueue(
                    message_id,
                    execution_id,
                    {
                        "to": destination,
                        "transport": "gmail_smtp",
                        "target_name": name,
                        "target_contact_email": contact,
                        "target_type": "group" if group_mode else "institution",
                        "competence": competence,
                        "due_date": due.isoformat(),
                        "subject": subject,
                        "body": body,
                        "artifacts": artifacts,
                        "target_ids": ids,
                        "group_id": target_id if group_mode else None,
                    },
                )
            statuses = self.dispatch(execution_id)
            if any(status != "submitted" for status in statuses):
                result.errors.append("delivery_requires_attention")
            result.status = "partial" if result.errors else "completed"
        except BaseException:
            result.status = "failed"
            self.repo.finish_execution(execution_id, result.status, asdict(result))
            raise
        self.repo.finish_execution(execution_id, result.status, asdict(result))
        self.repo.audit(identity.subject, "deliveries.run", execution_id, result.status)
        return result

    def dispatch(self, execution_id):
        statuses = []
        for row in self.repo.outbox(execution_id):
            if row["status"] != "pending":
                statuses.append(row["status"])
                continue
            try:
                # Resolve current owner grants for every submission; never trust a saved UI session.
                identity = self.identities.resolve(self.repo.execution_owner(execution_id))
                payload = json.loads(row["payload"])
                self.policy.require(
                    identity,
                    "deliveries.send",
                    payload["target_ids"],
                    [payload["group_id"]] if payload["group_id"] else [],
                )
                if (payload.get("transport") != "gmail_smtp"
                        or payload.get("to") != self.mail_to
                        or len(payload["artifacts"]) != 2):
                    raise ValidationError("Mensagem incompatível com envio Gmail; recrie a automação.")
                attachments = []
                kinds = []
                for artifact_id in payload["artifacts"]:
                    artifact, data = self.history.download(identity, artifact_id)
                    kinds.append(artifact.kind)
                    if not data.startswith(b"%PDF-"):
                        raise ValidationError("Anexo PDF inválido.")
                    attachments.append((artifact.filename, data))
                if sorted(kinds) != ["invoice", "report"]:
                    raise ValidationError("Envio exige uma fatura e um relatório.")
                notification = Notification(
                    payload["to"],
                    payload["subject"],
                    payload["body"],
                    tuple(attachments),
                    None,
                    f"<{row['id']}@sar.invalid>",
                )
                if not self.repo.claim_message(row["id"]):
                    continue
                self.notifications.send(notification)
            except DeliveryUncertain:
                status = "indeterminate"
            except SarError:
                status = "blocked"
            except Exception:
                # Conservative for unexpected transport errors; avoid duplicate delivery.
                status = "indeterminate"
            else:
                status = "submitted"
            self.repo.message_status(row["id"], status, smtp_accepted=status == "submitted")
            statuses.append(status)
        return statuses

    @staticmethod
    def _message(name, period, due):
        subject = f"[SAR] - Fatura e Relatório Consolidado — {name}"
        body = (
            f"Olá, equipe {name},\n\n"
            "Segue em anexo a Fatura Comercial consolidada e o Relatório Técnico de Monitoramento "
            f"referente a {period.text}.\n\n"
            f"A fatura possui vencimento para o dia {due:%d/%m/%Y}.\n\n"
            "Em caso de dúvidas, nossa equipe do PoP-CE está à disposição."
        )
        return subject, body
