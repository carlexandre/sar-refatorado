import hashlib
from datetime import date, datetime, timedelta
from sar.domain.errors import AccessDenied, ValidationError


class History:
    def __init__(self, repo, store, policy):
        self.repo, self.store, self.policy = repo, store, policy

    def list(
        self, identity, search="", group="Todos", time_filter="Todo o tempo", start=None, end=None, today=None
    ):
        self.policy.require(identity, "reports.read")
        today = today or date.today()
        lower, upper = None, None
        days = {"Hoje": 0, "Últimos 7 dias": 7, "Últimos 30 dias": 30, "Últimos 3 meses": 90}
        if time_filter in days:
            lower = today - timedelta(days=days[time_filter])
        elif time_filter == "Personalizado":
            if not start or not end or start > end:
                raise ValidationError("Período de histórico inválido.")
            lower, upper = start, end + timedelta(days=1)
        result = []
        for row in self.repo.history():
            try:
                ids = self.repo.artifact_links(row["artifact_id"]) if row["artifact_id"] else [row["link_id"]]
                self.policy.require(identity, "reports.read", ids)
                if row["artifact_id"] and self.repo.artifact_unknown_scope(row["artifact_id"]):
                    self.policy.require(identity, "admin.diagnostics")
            except AccessDenied:
                continue
            if search.casefold() not in row["nome_instituicao"].casefold():
                continue
            if group != "Todos" and row["grupo"] != group:
                continue
            created = datetime.fromisoformat(row["data_geracao"]).date()
            if (lower and created < lower) or (upper and created >= upper):
                continue
            result.append(row)
        return result

    def download(self, identity, artifact_id):
        artifact = self.repo.artifact(artifact_id)
        action = "billing.read" if artifact.kind == "invoice" else "reports.read"
        self.policy.require(identity, action, self.repo.artifact_links(artifact_id))
        if self.repo.artifact_unknown_scope(artifact_id):
            self.policy.require(identity, "admin.diagnostics")
        data = self.store.read(artifact_id)
        if hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise ValidationError("Falha de integridade do documento.")
        self.repo.audit(identity.subject, f"{artifact.kind}.download", artifact_id)
        return artifact, data
