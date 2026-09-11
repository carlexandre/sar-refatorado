from dataclasses import asdict
from datetime import date
import json
import uuid
from sar.domain.errors import DeliveryUncertain, SarError, ValidationError
from sar.domain.models import ExecutionResult, Notification
from sar.domain.periods import due_date, reference
from sar.security.validation import email


class Deliveries:
    def __init__(self, repo, reports, invoices, history, notifications, identities, policy):
        self.repo, self.reports, self.invoices, self.history = repo, reports, invoices, history
        self.notifications, self.identities, self.policy = notifications, identities, policy

    def run(self, identity, request, *, occurrence=None, schedule_id=None):
        self.policy.require(identity, "deliveries.send")
        if request.group_id and request.link_ids:
            raise ValidationError("Selecione grupo ou instituições, não ambos.")
        today = request.today or date.today()
        period, competence = reference(today, request.start, request.end)
        due = due_date(today, request.invoice_due_day)
        if request.group_id:
            group = self.repo.group(request.group_id)
            ids = self.repo.group_links(group.id)
            self.policy.require(identity, "deliveries.send", ids, [group.id])
            targets = [(group.id, group.nome, group.email_contato, ids, True)]
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
                (link.id, link.nome_instituicao, link.email_contato, [link.id], False) for link in links
            ]
        execution_id = uuid.uuid4().hex
        if not self.repo.start_execution(
            execution_id, occurrence or f"manual:{execution_id}", identity.subject, schedule_id
        ):
            return ExecutionResult("", "duplicate")
        result = ExecutionResult(execution_id, "running")
        try:
            for target_id, name, destination, ids, group_mode in targets:
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
                if request.include_invoice:
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
                if not destination:
                    result.errors.append(f"target:{target_id}:no_recipient")
                    continue
                subject, body = self._message(name, competence, due, request.include_invoice, group_mode)
                message_id = uuid.uuid4().hex
                self.repo.enqueue(
                    message_id,
                    execution_id,
                    {
                        "to": destination,
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
                attachments = []
                for artifact_id in payload["artifacts"]:
                    artifact, data = self.history.download(identity, artifact_id)
                    attachments.append((artifact.filename, data))
                reply_to = None
                if identity.verified_email and identity.email:
                    try:
                        reply_to = email(identity.email)
                    except ValidationError:
                        pass
                notification = Notification(
                    payload["to"],
                    payload["subject"],
                    payload["body"],
                    tuple(attachments),
                    reply_to,
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
            self.repo.message_status(row["id"], status)
            statuses.append(status)
        return statuses

    @staticmethod
    def _message(name, competence, due, include_invoice, group):
        if group:
            subject = (
                f"Fatura e Relatório Consolidado — {competence} ({name})"
                if include_invoice
                else f"Relatório Consolidado de Tráfego — {competence} ({name})"
            )
            body = f"Olá, equipe {name},\n\nSegue em anexo {'a Fatura Comercial consolidada e ' if include_invoice else ''}o Relatório Técnico de Monitoramento referente ao {competence}.\n"
        else:
            subject = (
                f"Fatura e Relatório de Tráfego GigaFOR — {competence} ({name})"
                if include_invoice
                else f"Relatório de Tráfego GigaFOR — {competence} ({name})"
            )
            body = f"Olá, equipe da {name},\n\nSegue em anexo {'a Fatura Comercial e ' if include_invoice else ''}o Relatório Técnico de Monitoramento de Tráfego referente ao {competence}.\n"
        if include_invoice:
            body += f"\nA fatura possui vencimento para o dia {due:%d/%m/%Y}.\n"
        body += "\nEm caso de dúvidas, nossa equipe do PoP-CE está à disposição.\n\nAtenciosamente,\nSistema de Automatização de Relatórios (SAR)\nPoP-CE / RNP"
        return subject, body
