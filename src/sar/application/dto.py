"""Application input/output contracts shared by UI and CLI."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RunRequest:
    link_ids: tuple[int, ...] = ()
    group_id: int | None = None
    include_invoice: bool = False
    invoice_due_day: int = 15
    start: str | None = None
    end: str | None = None
    today: date | None = None
