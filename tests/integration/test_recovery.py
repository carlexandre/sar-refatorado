from dataclasses import replace
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import pytest
from sar.application.dto import RunRequest
from sar.application.services.recovery import Recovery
from sar.domain.errors import ValidationError, DeliveryUncertain, AccessDenied
from sar.domain.models import Schedule
from sar.security.identity import Identity


def test_execution_claim_is_atomic(app):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda value: app.repo.start_execution(str(value), "same-occurrence", "internal-team"),
                range(2),
            )
        )
    assert sorted(results) == [False, True]


def test_message_claim_is_atomic(app):
    app.repo.start_execution("execution", "occurrence", "internal-team")
    app.repo.enqueue("message", "execution", {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: app.repo.claim_message("message"), range(2)))
    assert sorted(results) == [False, True]


def test_reconcile_retry_is_separate_from_sending(app):
    def uncertain(notification):
        raise DeliveryUncertain("unknown")

    app.deliveries.notifications.send = uncertain
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=date(2024, 3, 5)))
    message = app.repo.outbox(result.id)[0]
    service = Recovery(app.repo, app.policy)
    service.reconcile(app.identities.current(), message["id"], "retry", "TEST-123")
    assert app.repo.outbox(result.id)[0]["status"] == "pending"
    sent = []
    app.deliveries.notifications.send = lambda notification: sent.append(notification)
    assert not sent
    assert app.deliveries.dispatch(result.id) == ["submitted"]
    assert len(sent) == 1
    with pytest.raises(ValidationError):
        service.reconcile(app.identities.current(), message["id"], "retry", "TEST-123")


def test_pause_invalid_contact(app):
    actor = app.identities.current()
    key = app.schedules.save(actor, Schedule(0, (1,), 5, "08:00"))
    app.repo.save_institution(replace(app.repo.institution(1), email_contato=""))
    app.schedules.toggle(actor, key)
    assert not app.repo.schedule(key).ativo
    with pytest.raises(ValidationError):
        app.schedules.toggle(actor, key)


def test_technical_group_edit_cannot_change_billing(app):
    actor = Identity("operator", frozenset({"operations"}), global_scope=True)
    group = app.repo.group(1)
    app.registrations.save_group(actor, replace(group, nome="Renamed", fatura_para="injected"))
    assert app.repo.group(1).nome == "Renamed"
    assert app.repo.group(1).fatura_para == group.fatura_para


def test_dispatch_revalidates_owner_and_uses_verified_email(app):
    actor = Identity(
        "directory-user",
        frozenset({"billing"}),
        global_scope=True,
        email="user@example.org",
        verified_email=True,
    )

    class Provider:
        def resolve(self, subject):
            assert subject == actor.subject
            return actor

    app.deliveries.identities = Provider()
    result = app.deliveries.run(actor, RunRequest((1,), today=date(2024, 3, 5)))
    assert result.status == "completed"
    assert app.deliveries.notifications.messages[0].reply_to == "user@example.org"


def test_global_diagnostics_denied_to_scoped_admin(app):
    with pytest.raises(AccessDenied):
        app.schedules.diagnostics(Identity("limited-admin", frozenset({"administration"})))
