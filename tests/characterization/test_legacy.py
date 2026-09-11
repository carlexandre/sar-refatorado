"""Golden-master comparison against frozen source, never importing the running legacy app."""

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import fitz
import pandas as pd
import pytest
from sar.domain.periods import previous_month
from sar.infrastructure.documents.renderer import Documents
from sar.infrastructure.documents.report_renderer import criar_pdf_completo
from sar.infrastructure.documents.invoice_renderer import criar_fatura_pdf
from sar.infrastructure.documents.templates import ROOT

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "legacy"


def legacy_module(name):
    namespace = {"__name__": "frozen_legacy"}
    source = (FIXTURES / (name + ".py.txt")).read_text(encoding="utf-8")
    exec(compile(source, str(FIXTURES / name), "exec"), namespace)
    return namespace


def compare_pdf(before, after):
    old, new = fitz.open(stream=before, filetype="pdf"), fitz.open(stream=after, filetype="pdf")
    assert len(old) == len(new)
    for page_a, page_b in zip(old, new):
        assert page_a.get_text() == page_b.get_text()
        pix_a, pix_b = page_a.get_pixmap(), page_b.get_pixmap()
        assert pix_a.samples == pix_b.samples


@pytest.mark.parametrize("count", [1, 3])
def test_report_pdf_visual_equivalence(monkeypatch, count):
    # cwd contains only packaged assets, never the legacy DB or scripts.
    monkeypatch.chdir(ROOT)
    old = legacy_module("gerador_relatorio")
    period = previous_month(date(2024, 3, 1))
    data = [
        {
            "infos": {"instituicao": f"Instituição {i}", "capacidade": "1 Gbps"},
            "stats": {"media_in": 12.5, "media_out": 23.5, "max_in": 900, "max_out": 300},
            "alertas": [
                {
                    "trigger": "Bandwidth high",
                    "data": "01/02 12:30",
                    "duracao": "Ativo/S.Rec.",
                    "host": "Host",
                }
            ],
            "grafico_bytes": None,
        }
        for i in range(count)
    ]
    compare_pdf(
        old["criar_pdf_completo"](data, period.start, period.end),
        criar_pdf_completo(data, period.start, period.end),
    )


@pytest.mark.parametrize(
    "items", [[], [{"descricao": "Conectividade à Rede GigaFOR", "quantidade": 3, "valor_unitario": 12.50}]]
)
def test_invoice_pdf_visual_equivalence(monkeypatch, items):
    monkeypatch.chdir(ROOT)
    old = legacy_module("gerador_fatura")
    data = {
        "cliente_nome": "Instituição de Pesquisa e Educação",
        "cliente_cnpj": "00.000.000/0001-00",
        "cliente_end": "Rua de Teste",
        "cliente_cidade": "Fortaleza",
        "cliente_uf": "CE",
        "cliente_cep": "00000-000",
        "fatura_num": "FAT-022024-1",
        "fatura_data": "05/03/2024",
        "fatura_venc": "15/03/2024",
        "periodo_str": "Mês de 02/2024",
        "itens": items,
    }
    compare_pdf(old["criar_fatura_pdf"](data), criar_fatura_pdf(data))


def test_processing_matches_frozen_legacy(app):
    source = (FIXTURES / "zabbix_service.py.txt").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "processar_dados_instituicao"
    )
    namespace = {
        "pd": pd,
        "db": SimpleNamespace(conectar=app.repo.database.connect),
        "gerar_grafico_matplotlib": lambda *args: None,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "frozen_processor", "exec"), namespace)
    gateway = app.monitoring
    api = SimpleNamespace(
        history=SimpleNamespace(
            get=lambda **kw: gateway.history(kw["itemids"][0], kw["time_from"], kw["time_till"])
        ),
        trend=SimpleNamespace(
            get=lambda **kw: gateway.trends(kw["itemids"][0], kw["time_from"], kw["time_till"])
        ),
        event=SimpleNamespace(
            get=lambda **kw: (
                gateway.recoveries(kw["eventids"])
                if "eventids" in kw
                else gateway.events(kw["hostids"][0], kw["time_from"], kw["time_till"])
            )
        ),
    )
    period = previous_month(date(2024, 3, 1))
    old = namespace["processar_dados_instituicao"](api, 1, period.start, period.end)
    new = app.reports.data(app.identities.current(), 1, period)
    assert new.stats == old["stats"]
    assert new.infos == old["infos"]
    assert new.alerts == old["alertas"]


def test_real_chart_and_pdf(app):
    period = previous_month(date(2024, 3, 1))
    report = app.reports.data(app.identities.current(), 1, period)
    content = Documents().report([report], period)
    document = fitz.open(stream=content, filetype="pdf")
    assert len(document) >= 3
    assert any(page.get_images() for page in document)
