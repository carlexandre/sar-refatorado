from datetime import date, datetime, timedelta, timezone
from sar.domain.errors import ValidationError
from sar.domain.models import Period


def validate_period(start: date, end: date) -> Period:
    if start > end:
        raise ValidationError("A data inicial deve ser anterior ou igual à final.")
    return Period(start, end)


def previous_month(today: date) -> Period:
    end = today.replace(day=1) - timedelta(days=1)
    return Period(end.replace(day=1), end)


def reference(today: date, start: str | None = None, end: str | None = None):
    if bool(start) != bool(end):
        raise ValidationError("Informe as duas datas do período.")
    if start:
        try:
            period = validate_period(date.fromisoformat(start), date.fromisoformat(end))
        except ValueError:
            raise ValidationError("Datas devem estar no formato YYYY-MM-DD.") from None
        return period, period.text
    period = previous_month(today)
    return period, f"Mês de {period.start:%m/%Y}"


def timestamps(period: Period) -> tuple[int, int]:
    # Preserve pandas' legacy naive Timestamp.timestamp() (UTC), including upper endpoint.
    start = int(datetime.combine(period.start, datetime.min.time(), timezone.utc).timestamp())
    end = int(datetime.combine(period.end, datetime.min.time(), timezone.utc).timestamp()) + 86400
    return start, end


def due_date(today: date, day: int) -> date:
    if not 1 <= day <= 28:
        raise ValidationError("Dia de vencimento deve estar entre 1 e 28.")
    return today.replace(day=day)
