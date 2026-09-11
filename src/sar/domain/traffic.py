from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def needs_trends(records: list[dict], start: int) -> bool:
    return not records or min(int(r["clock"]) for r in records) - start > 86400


def statistics(records: list[dict], trends: bool) -> tuple[float, float]:
    peaks = [float(r["value_max" if trends else "value"]) for r in records]
    averages = [float(r["value_avg" if trends else "value"]) for r in records]
    return max(peaks) / 1_000_000, sum(averages) / len(averages) / 1_000_000


def align_series(incoming: list[dict], outgoing: list[dict], trend_in: bool, trend_out: bool):
    # Preserve outer merge, ffill and initial zero fill without depending on pandas.
    def index(rows, trend):
        result = {}
        for row in rows:
            result.setdefault(int(row["clock"]), []).append(float(row["value_max" if trend else "value"]))
        return result

    ins, outs = index(incoming, trend_in), index(outgoing, trend_out)
    result = []
    last_in = last_out = 0.0
    for clock in sorted(ins.keys() | outs.keys()):
        for value_in in ins.get(clock, [last_in]):
            for value_out in outs.get(clock, [last_out]):
                result.append(
                    {"clock": clock, "recv_mbps": value_in / 1_000_000, "sent_mbps": value_out / 1_000_000}
                )
                last_in, last_out = value_in, value_out
    return result


def alerts(events: list[dict], recoveries: list[dict], name: str):
    recovered = {str(r["eventid"]): int(r["clock"]) for r in recoveries}
    result = []
    for event in events:
        if not any(term in event["name"].lower() for term in ("bandwidth", "uptime", "restart")):
            continue
        duration = "Ativo/S.Rec."
        recovery = recovered.get(str(event.get("r_eventid")))
        if recovery is not None:
            seconds = recovery - int(event["clock"])
            days, rest = divmod(seconds, 86400)
            hours, rest = divmod(rest, 3600)
            minutes, seconds = divmod(rest, 60)
            parts = [f"{v}{unit}" for v, unit in zip((days, hours, minutes), ("d", "h", "m")) if v > 0]
            duration = " ".join(parts or [f"{seconds}s"])
        when = datetime.fromtimestamp(int(event["clock"]), timezone.utc).astimezone(
            ZoneInfo("America/Fortaleza")
        )
        result.append(
            {
                "data": when.strftime("%d/%m %H:%M"),
                "trigger": event["name"],
                "duracao": duration,
                "host": name,
            }
        )
    return result


def utilization(stats: dict, capacity: str) -> tuple[float, str]:
    mbps = 1000.0
    try:
        value, unit = capacity.strip().split(maxsplit=1)
        if "gbps" in unit.lower():
            mbps = float(value.replace(",", ".")) * 1000
        elif "mbps" in unit.lower():
            mbps = float(value.replace(",", "."))
    except (ValueError, AttributeError):
        pass
    percentage = max(stats.get("max_in", 0), stats.get("max_out", 0)) / mbps * 100 if mbps > 0 else 0
    return percentage, "critical" if percentage >= 90 else "high" if percentage >= 75 else "normal"
