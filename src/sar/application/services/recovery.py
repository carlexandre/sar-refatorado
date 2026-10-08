import json
from sar.domain.errors import ValidationError
from sar.security.validation import text


class Recovery:
    def __init__(self, repo, policy):
        self.repo, self.policy = repo, policy

    def messages(self, identity):
        self.policy.require(identity, "admin.diagnostics")
        messages = []
        for row in self.repo.outbox():
            payload = json.loads(row["payload"])
            item = {key: row[key] for key in (
                "id", "execution_id", "status", "attempts", "updated_at", "smtp_accepted_at"
            )}
            item.update(target=payload.get("target_name"), recipient=payload.get("to"),
                        transport=payload.get("transport", "legacy_smtp"))
            if row["status"] == "submitted":
                item["result"] = (
                    "Aceito pelo Gmail (SMTP)" if row["smtp_accepted_at"]
                    and payload.get("transport") == "gmail_smtp" else "Submissão registrada; sem confirmação Gmail"
                )
            else:
                item["result"] = row["status"]
            messages.append(item)
        return messages

    def reconcile(self, identity, message_id, decision, reason):
        self.policy.require(identity, "admin.diagnostics")
        if decision not in {"submitted", "retry", "cancelled"}:
            raise ValidationError("Decisão de reconciliação inválida.")
        text(reason, "Motivo", required=True)
        self.repo.reconcile_message(message_id, "pending" if decision == "retry" else decision)
        self.repo.audit(identity.subject, "outbox.reconcile", message_id, f"{decision}: {reason}")
