from datetime import date
import pytest
from sar.domain.periods import previous_month, reference, timestamps, due_date, validate_period
from sar.domain.models import InvoiceItem
from sar.domain.billing import total
from sar.domain.traffic import needs_trends, statistics, align_series, alerts, utilization
from sar.domain.errors import ValidationError


@pytest.mark.parametrize(
    "today,start,end",
    [
        (date(2024, 3, 2), date(2024, 2, 1), date(2024, 2, 29)),
        (date(2025, 1, 1), date(2024, 12, 1), date(2024, 12, 31)),
    ],
)
def test_previous_month(today, start, end):
    assert previous_month(today).start == start
    assert previous_month(today).end == end


def test_period_end_and_validation():
    period, text = reference(date(2024, 2, 1), "2024-01-01", "2024-01-01")
    assert timestamps(period)[1] - timestamps(period)[0] == 86400
    assert text == "01/01/2024 a 01/01/2024"
    with pytest.raises(ValidationError):
        reference(date.today(), "2024-01-01", None)
    with pytest.raises(ValidationError):
        validate_period(date(2024, 2, 2), date(2024, 2, 1))
    with pytest.raises(ValidationError):
        due_date(date(2024, 2, 1), 31)


def test_trends_threshold_and_stats():
    assert needs_trends([], 0)
    assert not needs_trends([{"clock": "86400"}], 0)
    assert needs_trends([{"clock": "86401"}], 0)
    assert statistics(
        [{"value_avg": "1000000", "value_max": "9000000"}, {"value_avg": "3000000", "value_max": "5000000"}],
        True,
    ) == (9, 2)
    assert statistics([{"value": "1000000"}, {"value": "3000000"}], False) == (3, 2)


def test_outer_merge_and_forward_fill():
    data = align_series(
        [{"clock": "1", "value": "1000000"}, {"clock": "3", "value": "3000000"}],
        [{"clock": "2", "value": "2000000"}],
        False,
        False,
    )
    assert [(r["recv_mbps"], r["sent_mbps"]) for r in data] == [(1, 0), (1, 2), (3, 2)]


@pytest.mark.parametrize("peak,expected", [(749, "normal"), (750, "high"), (900, "critical")])
def test_utilization(peak, expected):
    assert utilization({"max_in": peak}, "1 Gbps")[1] == expected


@pytest.mark.parametrize(
    "capacity,peak,percentage,status",
    [
        ("10Gbps", 986.41, 9.8641, "normal"),
        ("10 Gbps", 986.41, 9.8641, "normal"),
        ("1Gbps", 986.41, 98.641, "critical"),
        ("500 Mbps", 450, 90.0, "critical"),
        ("1,5 Gbps", 750, 50.0, "normal"),
    ],
)
def test_utilization_uses_declared_capacity(capacity, peak, percentage, status):
    actual, actual_status = utilization({"max_in": 0, "max_out": peak}, capacity)
    assert actual == pytest.approx(percentage)
    assert actual_status == status


def test_utilization_never_guesses_an_unrecognized_capacity():
    assert utilization({"max_out": 986.41}, "capacidade desconhecida") == (None, "unknown")


def test_alert_filter_duration_timezone():
    events = [
        {"name": "Bandwidth", "clock": "0", "r_eventid": "2"},
        {"name": "CPU", "clock": "0", "r_eventid": "0"},
    ]
    result = alerts(events, [{"eventid": "2", "clock": "3661"}], "Host")
    assert len(result) == 1
    assert result[0]["duracao"] == "1h 1m"
    assert result[0]["data"] == "31/12 21:00"


def test_float_total_compatibility():
    assert total([InvoiceItem("a", 3, 0.1)]) == 3 * 0.1
