from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path
import sqlite3
import uuid

import pytest

from sar.domain.errors import AccessDenied
from sar.domain.models import AppUser, Group, InvoiceTemplateOverride
from sar.infrastructure.persistence.sqlite import initialize
from sar.security.authentication import AuthenticationService, IdentityDirectory, PasswordHasher


def test_existing_v1_database_is_migrated_to_v2(tmp_path):
    path = tmp_path / "sar.db"
    initial = Path(__file__).resolve().parents[2] / "src" / "sar" / "migrations" / "001_initial.sql"
    with sqlite3.connect(path) as connection:
        connection.executescript(initial.read_text(encoding="utf-8"))
    initialize(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [(1,), (2,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_local_login_session_scopes_and_lockout(app):
    hasher = PasswordHasher()
    user = AppUser(
        uuid.uuid4().hex, "billing.user", "Billing User", "billing@example.org",
        password_hash=hasher.hash("correct horse battery staple"), must_change_password=False,
    )
    app.repo.create_user(user, {"billing"}, group_ids={1})
    auth = AuthenticationService(app.repo, IdentityDirectory(app.repo), hasher)

    token = auth.login("BILLING.USER", "correct horse battery staple")
    identity = auth.current(token)
    assert identity.roles == frozenset({"billing"})
    assert identity.institution_ids == frozenset({1, 2, 3, 4})
    auth.logout(token)
    with pytest.raises(AccessDenied):
        auth.current(token)

    for _ in range(5):
        with pytest.raises(AccessDenied):
            auth.login("billing.user", "wrong password")
    assert app.repo.user(user.id).locked_until is not None
    with pytest.raises(AccessDenied):
        auth.login("billing.user", "correct horse battery staple")


def test_template_inheritance_and_optimistic_revision(app):
    actor = app.identities.current()
    child = app.repo.save_group(Group(0, "Child", parent_id=1))
    app.repo.save_institution(replace(app.repo.institution(1), grupo_id=child))
    app.templates.save(actor, InvoiceTemplateOverride(title_text="Default title"))
    app.templates.save(actor, InvoiceTemplateOverride(group_id=1, payment_terms="Root terms"))
    link_template = InvoiceTemplateOverride(
        link_id=1, observation_mode="show", observation_text="Institution note", primary_color="#112233"
    )
    template_id = app.templates.save(actor, link_template)

    resolved = app.templates.resolve(actor, 1)
    assert resolved.title_text == "Default title"
    assert resolved.payment_terms == "Root terms"
    assert resolved.show_observation and resolved.observation_text == "Institution note"
    assert resolved.primary_color == "#112233"

    current = app.repo.template_override(link_id=1)
    app.templates.save(actor, replace(current, observation_text="Updated"))
    with pytest.raises(Exception):
        app.templates.save(actor, replace(current, observation_text="Stale"))
    assert app.repo.template_override(link_id=1).id == template_id


def test_preview_concurrency_idempotency_and_void(app):
    actor = app.identities.current()
    today = date(2026, 9, 10)
    before = app.repo.invoice_sequence(1).next_value
    preview = app.invoices.preview(actor, 1, today, today, "setembro de 2026")
    assert preview.startswith(b"%PDF-")
    assert app.repo.invoice_sequence(1).next_value == before

    def issue(key):
        return app.invoices.issue(actor, 1, today, today, "setembro de 2026", key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        artifacts = list(pool.map(issue, ("manual:a", "manual:b")))
    assert len({artifact.id for artifact in artifacts}) == 2
    ledger = app.repo.invoice_ledger()
    assert sorted(row["sequence_value"] for row in ledger if row["link_id"] == 1) == [before, before + 1]
    repeated = issue("manual:a")
    assert repeated.id == artifacts[0].id
    assert app.repo.invoice_sequence(1).next_value == before + 2

    first = next(row for row in ledger if row["artifact_id"] == artifacts[0].id)
    assert app.invoices.void(actor, first["id"], "Correção comercial")
    assert next(row for row in app.repo.invoice_ledger() if row["id"] == first["id"])["status"] == "void"


def test_render_failure_does_not_consume_number(app):
    actor = app.identities.current()
    before = app.repo.invoice_sequence(2).next_value
    original = app.invoices.documents.invoice
    app.invoices.documents.invoice = lambda data, template: (_ for _ in ()).throw(RuntimeError("render failed"))
    try:
        with pytest.raises(RuntimeError):
            app.invoices.issue(actor, 2, date.today(), date.today(), "mês", "manual:failure")
    finally:
        app.invoices.documents.invoice = original
    assert app.repo.invoice_sequence(2).next_value == before
    assert not app.repo.invoice_by_idempotency("manual:failure")
