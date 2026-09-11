import math
import re
from sar.domain.errors import ValidationError
from sar.domain.models import InvoiceItem, Schedule
from sar.domain.periods import reference
from datetime import date


def identifier(value) -> int:
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ValidationError("Identificador inválido.")
    return int(value)


def text(value: str, label: str, *, required=False, limit=500) -> str:
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValidationError(f"{label}: texto inválido ou longo demais.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{label} é obrigatório.")
    return value


def email(value: str, *, optional=False) -> str:
    value = text(value, "E-mail", limit=254)
    if optional and not value:
        return ""
    if not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value
    ):
        raise ValidationError("Informe um endereço de e-mail válido, sem nome de exibição.")
    return value


def filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:180] or "documento.pdf"


def items(values: list[InvoiceItem]) -> list[InvoiceItem]:
    result = []
    for item in values:
        description = text(item.descricao, "Descrição", limit=2000)
        if not description:
            continue
        if isinstance(item.quantidade, bool) or not isinstance(item.quantidade, int) or item.quantidade < 1:
            raise ValidationError("A quantidade deve ser um inteiro positivo.")
        if not math.isfinite(item.valor_unitario):
            raise ValidationError("Valor unitário inválido.")
        result.append(InvoiceItem(description, item.quantidade, item.valor_unitario))
    return result


def schedule(value: Schedule) -> None:
    if bool(value.grupo_id) == bool(value.link_ids):
        raise ValidationError("Selecione um grupo ou uma lista de instituições.")
    for item in value.link_ids:
        identifier(item)
    if value.grupo_id:
        identifier(value.grupo_id)
    if not 1 <= value.dia_envio <= 28 or not 1 <= value.fatura_venc_dia <= 28:
        raise ValidationError("Dias devem estar entre 1 e 28.")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value.horario):
        raise ValidationError("Horário inválido.")
    text(value.fatura_num_prefixo, "Prefixo", required=True, limit=100)
    if value.periodo_modo not in ("mes_anterior", "personalizado"):
        raise ValidationError("Modo de período inválido.")
    if value.periodo_modo == "personalizado":
        if not value.data_inicio or not value.data_fim:
            raise ValidationError("Informe as duas datas do período.")
        reference(date.today(), value.data_inicio, value.data_fim)
