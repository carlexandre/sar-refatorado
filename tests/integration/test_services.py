from dataclasses import replace
from datetime import date
import pytest
from sar.application.dto import RunRequest
from sar.domain.models import Schedule, Group
from sar.domain.errors import ValidationError, DeliveryUncertain
from sar.domain.periods import previous_month


def test_manual_limit_and_partial_history(app):
    actor = app.identities.current()
    with pytest.raises(ValidationError):
        app.reports.generate(actor, [1, 2, 3, 4], previous_month(date(2024, 3, 1)))
    original = app.reports.data
    app.reports.data = lambda identity, key, period: None if key == 2 else original(identity, key, period)
    result = app.reports.generate(actor, [1, 2], previous_month(date(2024, 3, 1)))
    assert result.included_ids == (1,) and result.skipped_ids == (2,)
    assert [r["link_id"] for r in app.repo.history()] == [1]


def test_group_items_are_not_sum_of_members(app):
    seen = []
    app.invoices.documents.invoice = lambda data, template: seen.append(data) or b"%PDF-1.7 test"
    app.invoices.generate(app.identities.current(), 1, "FAT", date.today(), date.today(), "month", group=True)
    assert seen[0]["itens"] == [{"descricao": "Grupo exclusivo", "quantidade": 1, "valor_unitario": 100.0}]


def test_schedule_conflict_recursive_and_reactivation(app):
    actor = app.identities.current()
    child = app.repo.save_group(Group(0, "Subgrupo", parent_id=1, email_contato="sub@example.org"))
    app.repo.save_institution(replace(app.repo.institution(1), grupo_id=child))
    first = app.schedules.save(actor, Schedule(0, (), 5, "08:00", grupo_id=1))
    with pytest.raises(ValidationError):
        app.schedules.save(actor, Schedule(0, (1,), 7, "09:00"))
    app.schedules.toggle(actor, first)
    app.schedules.save(actor, Schedule(0, (1,), 7, "09:00"))
    with pytest.raises(ValidationError):
        app.schedules.toggle(actor, first)


def test_references_prevent_orphans(app):
    with pytest.raises(ValidationError):
        app.registrations.delete_institution(app.identities.current(), 1)
    with pytest.raises(ValidationError):
        app.registrations.delete_group(app.identities.current(), 1)
    with app.repo.database.connect() as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_delivery_duplicate_outbox(app):
    actor = app.identities.current()
    request = RunRequest((1,), include_invoice=True, today=date(2024, 3, 5))
    first = app.deliveries.run(actor, request, occurrence="test")
    second = app.deliveries.run(actor, request, occurrence="test")
    assert first.status == "completed" and second.status == "duplicate"
    assert len(app.deliveries.notifications.messages) == 1
    assert len(app.deliveries.notifications.messages[0].attachments) == 2
    assert app.repo.outbox(first.id)[0]["status"] == "submitted"
    app.deliveries.dispatch(first.id)
    assert len(app.deliveries.notifications.messages) == 1


def test_uncertain_does_not_resend(app):
    def uncertain(notification):
        raise DeliveryUncertain("Indeterminado")

    app.deliveries.notifications.send = uncertain
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=date(2024, 3, 5)))
    assert result.status == "partial"
    assert app.repo.outbox(result.id)[0]["status"] == "indeterminate"
    assert app.deliveries.dispatch(result.id) == ["indeterminate"]


def test_recover_interrupted(app):
    app.repo.start_execution("execution", "unique", "internal-team")
    app.repo.enqueue("message", "execution", {})
    assert app.repo.claim_message("message")
    app.repo.recover_interrupted()
    assert app.repo.outbox()[0]["status"] == "indeterminate"
    assert app.repo.executions()[0]["status"] == "interrupted"


def test_atomic_profile_update(app):
    original = app.repo.profile(1)
    with pytest.raises(Exception):
        app.repo.save_profiles([replace(original, fatura_para="changed"), replace(original, link_id=999)], [])
    assert app.repo.profile(1).fatura_para == original.fatura_para
