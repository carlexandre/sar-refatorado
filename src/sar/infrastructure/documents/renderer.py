from threading import RLock
from sar.domain.models import Period, ReportData

RENDER_LOCK = RLock()


class Documents:
    def report(self, data: list[ReportData], period: Period) -> bytes:
        import pandas as pd
        from sar.infrastructure.documents.charts import gerar_grafico_matplotlib
        from sar.infrastructure.documents.report_renderer import criar_pdf_completo

        with RENDER_LOCK:
            rendered = []
            for item in data:
                frame = pd.DataFrame(item.series)
                frame["clock"] = pd.to_datetime(frame["clock"], unit="s")
                graph = gerar_grafico_matplotlib(
                    frame,
                    item.infos["instituicao"],
                    item.infos["capacidade"],
                    period.text,
                    period.start,
                    period.end,
                )
                rendered.append(
                    {"infos": item.infos, "stats": item.stats, "alertas": item.alerts, "grafico_bytes": graph}
                )
            return criar_pdf_completo(rendered, period.start, period.end)

    def invoice(self, data: dict, template=None) -> bytes:
        from sar.infrastructure.documents.invoice_renderer import criar_fatura_pdf

        with RENDER_LOCK:
            return criar_fatura_pdf(data, template)
