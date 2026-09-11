"""Produce synthetic document fixtures and page images for visual review."""

from datetime import date
from pathlib import Path
import fitz
from sar.domain.models import ReportData, Period
from sar.domain.periods import timestamps
from sar.infrastructure.documents.renderer import Documents

root = Path(__file__).resolve().parents[1] / "tmp" / "pdfs"
root.mkdir(parents=True, exist_ok=True)
period = Period(date(2024, 2, 1), date(2024, 2, 29))
start, end = timestamps(period)
row = ReportData(
    1,
    {"instituicao": "Instituição de Pesquisa e Educação", "capacidade": "1 Gbps", "periodo": period.text},
    {"media_in": 250.0, "media_out": 150.0, "max_in": 900.0, "max_out": 600.0},
    [
        {
            "trigger": "Bandwidth high",
            "host": "Equipamento de teste",
            "data": "15/02 14:30",
            "duracao": "1h 2m",
        }
    ],
    [
        {"clock": clock, "recv_mbps": 250 + 150 * ((clock - start) // 86400 % 3), "sent_mbps": 150}
        for clock in range(start, end, 86400)
    ],
)
renderer = Documents()
files = {
    "report": renderer.report([row], period),
    "invoice": renderer.invoice(
        {
            "cliente_nome": "Instituição de Pesquisa e Educação",
            "cliente_cnpj": "00.000.000/0001-00",
            "cliente_end": "Rua de Teste",
            "cliente_num": "100",
            "cliente_cep": "00000-000",
            "cliente_cidade": "Fortaleza",
            "cliente_uf": "CE",
            "fatura_num": "FAT-022024-1",
            "fatura_data": "05/03/2024",
            "fatura_venc": "15/03/2024",
            "periodo_str": "Mês de 02/2024",
            "itens": [
                {"descricao": "Conectividade à Rede GigaFOR", "quantidade": 1, "valor_unitario": 1250.50}
            ],
        }
    ),
}
for name, data in files.items():
    (root / f"{name}.pdf").write_bytes(data)
    document = fitz.open(stream=data, filetype="pdf")
    for index, page in enumerate(document):
        page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(root / f"{name}-{index + 1}.png")
    print(f"{name}: {len(document)} pages")
