from dataclasses import replace
from datetime import date
import json
import sqlite3
from pathlib import Path
import pytest
from sar.application.dto import RunRequest
from sar.application.services.recovery import Recovery
from sar.cli.main import parser
from sar.domain.errors import AccessDenied, DeliveryUncertain, IntegrationError, ValidationError
from sar.domain.models import Schedule
from sar.infrastructure.persistence.sqlite import initialize
from sar.security.identity import Identity


TODAY = date(2024, 3, 5)


def test_fixed_target_metadata_and_acceptance(app):
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    assert result.status == "completed"
    msg = app.deliveries.notifications.messages[0]
    assert msg.to == "svc.popce@rnp.br" and msg.subject == "[SAR] - Fatura e Relatório Consolidado — Instituição A"
    assert msg.reply_to is None and len(msg.attachments) == 2
    assert "Olá, equipe Instituição A," in msg.body
    assert "referente a 01/02/2024 a 29/02/2024." in msg.body
    assert "A fatura possui vencimento para o dia 15/03/2024." in msg.body
    assert msg.body.endswith("Em caso de dúvidas, nossa equipe do PoP-CE está à disposição.")
    row = app.repo.outbox(result.id)[0]
    assert row["status"] == "submitted" and row["smtp_accepted_at"]
    payload = json.loads(row["payload"])
    assert payload["transport"] == "gmail_smtp" and payload["due_date"] == "2024-03-15"
    item = Recovery(app.repo, app.policy).messages(app.identities.current())[0]
    assert item["result"] == "Aceito pelo Gmail (SMTP)"


def test_group_sends_one_pair_and_multiple_institutions_send_separately(app):
    actor = app.identities.current()
    result = app.deliveries.run(actor, RunRequest(group_id=1, today=TODAY))
    assert result.status == "completed"
    assert len(app.deliveries.notifications.messages) == 1
    assert app.deliveries.notifications.messages[0].subject == "[SAR] - Fatura e Relatório Consolidado — Grupo"
    result = app.deliveries.run(actor, RunRequest((1, 2), today=TODAY))
    assert result.status == "completed"
    assert len(app.deliveries.notifications.messages) == 3
    assert all(len(msg.attachments) == 2 for msg in app.deliveries.notifications.messages)


@pytest.mark.parametrize("stage", ["report", "invoice"])
def test_generation_failure_never_sends_a_single_document(app, stage):
    def fail(*args, **kwargs):
        raise ValidationError("synthetic failure")
    if stage == "report":
        app.reports.generate = fail
    else:
        app.invoices.issue = fail
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    assert result.status == "partial"
    assert app.repo.outbox(result.id) == [] and app.deliveries.notifications.messages == []
    assert any(f"{stage}_unavailable" in error for error in result.errors)


def test_report_only_requests_and_schedules_are_rejected(app):
    actor = app.identities.current()
    with pytest.raises(ValidationError, match="juntos"):
        app.deliveries.run(actor, RunRequest((1,), include_invoice=False, today=TODAY))
    with pytest.raises(ValidationError, match="juntos"):
        app.schedules.save(actor, Schedule(0, (1,), 5, "08:00", incluir_fatura=False))
    assert app.repo.executions() == []
    assert parser().parse_args(["monthly"]).incluir_fatura
    assert parser().parse_args(["monthly", "--incluir-fatura"]).incluir_fatura


@pytest.mark.parametrize("failure,status", [(IntegrationError("failure"), "blocked"),
                                           (DeliveryUncertain("unknown"), "indeterminate")])
def test_no_acceptance_timestamp_for_failed_submissions(app, failure, status):
    def fail(notification):
        raise failure
    app.deliveries.notifications.send = fail
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    row = app.repo.outbox(result.id)[0]
    assert row["status"] == status and row["smtp_accepted_at"] is None
    app.deliveries.dispatch(result.id)
    assert app.repo.outbox(result.id)[0]["attempts"] == 1
    Recovery(app.repo, app.policy).reconcile(app.identities.current(), row["id"], "submitted", "manual review")
    row = app.repo.outbox(result.id)[0]
    assert row["status"] == "submitted" and row["smtp_accepted_at"] is None
    assert "Aceito pelo Gmail" not in Recovery(app.repo, app.policy).messages(app.identities.current())[0]["result"]


@pytest.mark.parametrize("damage", ["missing", "two_reports", "corrupt", "legacy"])
def test_dispatch_checks_pair_and_artifact_integrity(app, damage):
    app.deliveries.dispatch = lambda _: []
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    row = app.repo.outbox(result.id)[0]
    payload = json.loads(row["payload"])
    if damage == "missing":
        payload["artifacts"].pop()
    elif damage == "two_reports":
        payload["artifacts"][1] = payload["artifacts"][0]
    elif damage == "legacy":
        payload.pop("transport")
    else:
        artifact_id = payload["artifacts"][0]
        (app.history.store.root / f"{artifact_id}.pdf").write_bytes(b"corrupt")
    with app.repo.database.connect() as conn:
        conn.execute("UPDATE outbox SET payload=? WHERE id=?", (json.dumps(payload), row["id"]))
    from sar.application.services.deliveries import Deliveries
    assert Deliveries.dispatch(app.deliveries, result.id) == ["blocked"]
    assert not app.deliveries.notifications.messages
    assert app.repo.outbox(result.id)[0]["smtp_accepted_at"] is None


def test_permission_revocation_blocks_pending_send(app):
    original_dispatch = app.deliveries.dispatch
    app.deliveries.dispatch = lambda _: []
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    class Revoked:
        def resolve(self, subject):
            return Identity(subject, frozenset())
    app.deliveries.identities = Revoked()
    assert original_dispatch(result.id) == ["blocked"]
    assert not app.deliveries.notifications.messages
    with pytest.raises(AccessDenied):
        Recovery(app.repo, app.policy).messages(Identity("viewer", frozenset({"consultation"}), global_scope=True))


def test_v2_migration_preserves_old_submission_without_inventing_acceptance(tmp_path):
    db = tmp_path / "sar.db"
    root = Path(__file__).resolve().parents[2] / "src/sar/migrations"
    with sqlite3.connect(db) as conn:
        for name in ("001_initial.sql", "002_auth_templates_invoice_sequences.sql"):
            conn.executescript((root / name).read_text(encoding="utf-8"))
        conn.execute("INSERT INTO executions(id,occurrence,owner_id,status) VALUES ('e','o','internal-team','completed')")
        conn.execute("INSERT INTO outbox(id,execution_id,payload,status) VALUES ('m','e','{}','submitted')")
    initialize(db)
    initialize(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT status,smtp_accepted_at FROM outbox").fetchall() == [("submitted", None)]
        assert conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,)]
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_database_failure_after_acceptance_requires_reconciliation(app):
    original_status = app.repo.message_status
    def fail_status(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic disk error")
    app.repo.message_status = fail_status
    with pytest.raises(sqlite3.OperationalError):
        app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    row = app.repo.outbox()[0]
    assert row["status"] == "sending" and row["smtp_accepted_at"] is None
    assert len(app.deliveries.notifications.messages) == 1
    app.repo.message_status = original_status
    app.repo.recover_interrupted()
    assert app.deliveries.dispatch(row["execution_id"]) == ["indeterminate"]
    assert len(app.deliveries.notifications.messages) == 1


def test_retry_keeps_message_id_and_records_only_actual_acceptance(app):
    attempted = []
    def uncertain(notification):
        attempted.append(notification.message_id)
        raise DeliveryUncertain("unknown")
    app.deliveries.notifications.send = uncertain
    result = app.deliveries.run(app.identities.current(), RunRequest((1,), today=TODAY))
    row = app.repo.outbox(result.id)[0]
    Recovery(app.repo, app.policy).reconcile(app.identities.current(), row["id"], "retry", "verified not received")
    assert app.repo.outbox(result.id)[0]["smtp_accepted_at"] is None
    app.deliveries.notifications.send = lambda notification: attempted.append(notification.message_id)
    assert app.deliveries.dispatch(result.id) == ["submitted"]
    assert attempted[0] == attempted[1]
    assert app.repo.outbox(result.id)[0]["smtp_accepted_at"]


@pytest.mark.parametrize("group", [False, True])
def test_requested_subject_works_without_registered_contact(app, group):
    if group:
        app.repo.save_group(replace(app.repo.group(1), email_contato=""))
        request = RunRequest(group_id=1, today=TODAY)
        expected = "Grupo"
    else:
        app.repo.save_institution(replace(app.repo.institution(1), email_contato=""))
        request = RunRequest((1,), today=TODAY)
        expected = "Instituição A"
    result = app.deliveries.run(app.identities.current(), request)
    assert result.status == "completed"
    message = app.deliveries.notifications.messages[0]
    assert message.subject == f"[SAR] - Fatura e Relatório Consolidado — {expected}" and message.to == "svc.popce@rnp.br"
