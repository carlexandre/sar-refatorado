from sar.domain import traffic
from sar.domain.errors import ValidationError
from sar.domain.models import ReportData, ReportResult
from sar.domain.periods import timestamps, validate_period
from sar.security.validation import identifier


class Reports:
    def __init__(self, repo, monitoring, documents, store, policy):
        self.repo, self.monitoring, self.documents, self.store, self.policy = (
            repo,
            monitoring,
            documents,
            store,
            policy,
        )

    def data(self, identity, link_id, period):
        self.policy.require(identity, "reports.generate", [identifier(link_id)])
        link = self.repo.institution(link_id)
        start, end = timestamps(period)

        def fetch(item):
            rows = self.monitoring.history(item, start, end)
            trend = traffic.needs_trends(rows, start)
            return (self.monitoring.trends(item, start, end) if trend else rows), trend

        incoming, trend_in = fetch(link.item_down_id)
        outgoing, trend_out = fetch(link.item_up_id)
        if not incoming or not outgoing:
            return None
        max_in, mean_in = traffic.statistics(incoming, trend_in)
        max_out, mean_out = traffic.statistics(outgoing, trend_out)
        events = self.monitoring.events(link.host_id, start, end)
        recovery_ids = [e["r_eventid"] for e in events if e.get("r_eventid") and e["r_eventid"] != "0"]
        return ReportData(
            link_id,
            {
                "instituicao": link.nome_instituicao,
                "interface": "Interface de Borda",
                "periodo": period.text,
                "capacidade": link.capacidade_str,
            },
            {"max_in": max_in, "media_in": mean_in, "max_out": max_out, "media_out": mean_out},
            traffic.alerts(events, self.monitoring.recoveries(recovery_ids), link.nome_instituicao),
            traffic.align_series(incoming, outgoing, trend_in, trend_out),
        )

    def generate(
        self, identity, ids, period, *, manual=True, filename=None, history_period=None, partial=False
    ):
        validate_period(period.start, period.end)
        ids = list(dict.fromkeys(identifier(i) for i in ids))
        if not ids or (manual and len(ids) > 3):
            raise ValidationError(
                "Selecione de uma a três instituições." if manual else "Nenhuma instituição selecionada."
            )
        self.policy.require(identity, "reports.generate", ids)
        data, skipped = [], []
        for link_id in ids:
            try:
                row = self.data(identity, link_id, period)
            except Exception:
                if not partial:
                    raise
                skipped.append(link_id)
                continue
            if row:
                data.append(row)
            else:
                skipped.append(link_id)
        if not data:
            raise ValidationError("Nenhuma das instituições possui dados disponíveis para este período.")
        if not filename:
            prefix = (
                "Relatorio_Conjunto"
                if len(data) > 1
                else "Relatorio_" + data[0].infos["instituicao"].replace(" ", "_")
            )
            filename = f"{prefix}_{period.start:%Y%m%d}.pdf"
        artifact = self.store.save(self.documents.report(data, period), filename)
        included = tuple(row.link_id for row in data)
        try:
            self.repo.register_artifact(artifact, included, history_period or period.text)
        except BaseException:
            self.store.remove_unregistered(artifact.id)
            raise
        self.repo.audit(identity.subject, "reports.generate", artifact.id)
        return ReportResult(artifact, included, tuple(skipped))
