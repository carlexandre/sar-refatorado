from dataclasses import asdict, replace
from datetime import date
import json
import uuid

from sar.domain.billing import invoice_data
from sar.domain.errors import ConcurrencyError, ValidationError
from sar.domain.models import CommercialProfile, InvoiceSequence
from sar.security.validation import identifier, text
from sar.workers.locking import exclusive_lock


class Invoices:
    def __init__(self, repo, documents, store, policy, templates, lock_path):
        self.repo, self.documents, self.store, self.policy = repo, documents, store, policy
        self.templates, self.lock_path = templates, lock_path

    def _target(self, target_id, group):
        target_id = identifier(target_id)
        if group:
            profile = self.repo.group(target_id)
            return target_id, profile.nome, profile, self.repo.group_links(target_id)
        institution = self.repo.institution(target_id)
        profile = self.repo.profile(target_id) or CommercialProfile(target_id, institution.nome_instituicao)
        return target_id, institution.nome_instituicao, profile, [target_id]

    @staticmethod
    def _number(sequence):
        numeric = str(sequence.next_value).zfill(sequence.padding)
        return f"{sequence.prefix}-{numeric}" if sequence.prefix else numeric

    def sequence(self, identity, target_id, *, group=False):
        target_id, _, _, ids = self._target(target_id, group)
        self.policy.require(identity, "billing.sequence.read", ids, [target_id] if group else [])
        return self.repo.invoice_sequence(target_id, group)

    def save_sequence(self, identity, target_id, initial_value, prefix="FAT", padding=0, *, group=False, revision=1):
        target_id, _, _, ids = self._target(target_id, group)
        self.policy.require(identity, "billing.sequence.write", ids, [target_id] if group else [])
        try:
            initial_value, padding = int(initial_value), int(padding)
        except (TypeError, ValueError):
            raise ValidationError("Número inicial ou preenchimento inválido.") from None
        if initial_value <= 0 or not 0 <= padding <= 12:
            raise ValidationError("Número inicial ou preenchimento inválido.")
        prefix = text(prefix, "Prefixo", limit=30)
        current = self.repo.invoice_sequence(target_id, group)
        value = InvoiceSequence(
            current.id if current else 0, target_id if group else None, None if group else target_id,
            initial_value, current.next_value if current else initial_value, prefix, padding,
            revision if current else 1, identity.subject,
        )
        saved = self.repo.save_invoice_sequence(value)
        self.repo.audit(identity.subject, "billing.sequence.save", saved)
        return saved

    def preview(self, identity, target_id, issued: date, due: date, period_text: str, *, group=False):
        target_id, name, profile, ids = self._target(target_id, group)
        self.policy.require(identity, "billing.issue", ids, [target_id] if group else [])
        template = self.templates.resolve(identity, target_id, group=group)
        data = invoice_data(
            profile, name, self.repo.invoice_items(target_id, group), "PRÉVIA", issued, due,
            text(period_text, "Período", required=True, limit=500),
        )
        data["preview"] = True
        return self.documents.invoice(data, template)

    def issue(self, identity, target_id, issued: date, due: date, period_text: str,
              idempotency_key: str, *, group=False, execution_id=None, filename=None):
        target_id, name, profile, ids = self._target(target_id, group)
        self.policy.require(identity, "billing.issue", ids, [target_id] if group else [])
        idempotency_key = text(idempotency_key, "Chave idempotente", required=True, limit=200)
        period_text = text(period_text, "Período", required=True, limit=500)
        existing = self.repo.invoice_by_idempotency(idempotency_key)
        if existing:
            return self.repo.artifact(existing["artifact_id"])
        with exclusive_lock(self.lock_path, wait=True):
            existing = self.repo.invoice_by_idempotency(idempotency_key)
            if existing:
                return self.repo.artifact(existing["artifact_id"])
            for _ in range(3):
                sequence = self.repo.invoice_sequence(target_id, group)
                if not sequence:
                    raise ValidationError("Configure a sequência de fatura para este alvo antes de emitir.")
                template = self.templates.resolve(identity, target_id, group=group)
                number = self._number(sequence)
                data = invoice_data(
                    profile, name, self.repo.invoice_items(target_id, group), number, issued, due, period_text
                )
                content = self.documents.invoice(data, template)
                artifact = self.store.save(
                    content, filename or f"Fatura_Gigafor_{number}_{name.replace(' ', '_')}.pdf"
                )
                artifact = replace(artifact, template_version=template.base_version, kind="invoice")
                issuance_id = uuid.uuid4().hex
                snapshot = json.dumps(asdict(template), ensure_ascii=False, sort_keys=True)
                values = (
                    issuance_id, sequence.id, sequence.next_value, number, artifact.id, execution_id,
                    idempotency_key, issued.isoformat(), due.isoformat(), period_text,
                    template.base_version, snapshot, "issued", identity.subject,
                )
                try:
                    self.repo.register_invoice(
                        sequence_id=sequence.id, expected_value=sequence.next_value,
                        artifact=artifact, link_ids=ids, issuance=values,
                    )
                except ConcurrencyError:
                    self.store.remove_unregistered(artifact.id)
                    continue
                except BaseException:
                    self.store.remove_unregistered(artifact.id)
                    existing = self.repo.invoice_by_idempotency(idempotency_key)
                    if existing:
                        return self.repo.artifact(existing["artifact_id"])
                    raise
                self.repo.audit(identity.subject, "billing.issue", issuance_id)
                return artifact
        raise ConcurrencyError("Não foi possível reservar o próximo número. Tente novamente.")

    def ledger(self, identity):
        self.policy.require(identity, "billing.ledger.read")
        rows = self.repo.invoice_ledger()
        if identity.global_scope:
            return rows
        return [row for row in rows if
                (row["link_id"] and row["link_id"] in identity.institution_ids) or
                (row["group_id"] and row["group_id"] in identity.group_ids)]

    def void(self, identity, issuance_id, reason):
        self.policy.require(identity, "billing.ledger.void")
        reason = text(reason, "Justificativa", required=True, limit=1000)
        self.repo.void_invoice(issuance_id, identity.subject, reason)
        self.repo.audit(identity.subject, "billing.invoice.void", issuance_id)
        return True

    def generate(self, identity, target_id, number, issued, due, period_text, *, group=False, filename=None):
        """Compatibility shim; official numbering is always allocated by issue()."""
        return self.issue(identity, target_id, issued, due, period_text, f"legacy:{uuid.uuid4().hex}",
                          group=group, filename=filename)
