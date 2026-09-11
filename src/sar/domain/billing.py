from dataclasses import asdict
from datetime import date
from sar.domain.models import CommercialProfile, Group, InvoiceItem


def invoice_data(
    profile: CommercialProfile | Group,
    fallback_name: str,
    items: list[InvoiceItem],
    number: str,
    issued: date,
    due: date,
    period_text: str,
) -> dict:
    return {
        "cliente_nome": profile.fatura_para or fallback_name,
        "cliente_cnpj": profile.cnpj,
        "cliente_cep": profile.cep,
        "cliente_end": profile.endereco,
        "cliente_num": profile.numero,
        "cliente_cidade": profile.cidade,
        "cliente_uf": profile.uf,
        "fatura_num": number,
        "fatura_data": issued.strftime("%d/%m/%Y"),
        "fatura_venc": due.strftime("%d/%m/%Y"),
        "periodo_str": period_text,
        "itens": [asdict(item) for item in items],
    }


def total(items: list[InvoiceItem]) -> float:
    # Legacy float calculation deliberately retained; Decimal migration needs separate approval.
    return sum(item.quantidade * item.valor_unitario for item in items)


def currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
