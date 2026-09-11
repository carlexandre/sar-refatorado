from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
import pytest
from sar.domain.models import Schedule, Notification
from sar.domain.errors import (
    AccessDenied,
    ValidationError,
    ConfigurationError,
    IntegrationError,
    DeliveryUncertain,
)
from sar.domain.periods import previous_month
from sar.security.identity import Identity
from sar.security.validation import email
from sar.infrastructure.scheduling.cron import CronScheduler
from sar.infrastructure.email.smtp_relay import SMTPRelay
from sar.config.settings import Settings


@pytest.mark.parametrize(
    "value", ["alice@example.org\nBcc: evil@example.org", "bad", "a@example.org,b@example.org"]
)
def test_email_injection(value):
    with pytest.raises(ValidationError):
        email(value)


def test_scope_download_consolidated(app):
    admin = app.identities.current()
    result = app.reports.generate(admin, [1, 2], previous_month(date(2024, 3, 1)))
    viewer = Identity("viewer", frozenset({"consultation"}), frozenset({1}))
    with pytest.raises(AccessDenied):
        app.history.download(viewer, result.artifact.id)
    assert app.history.list(viewer) == []
    allowed = replace(viewer, institution_ids=frozenset({1, 2}))
    assert app.history.download(allowed, result.artifact.id)[1].startswith(b"%PDF")


def test_deny_default_and_expired(app):
    for identity in (
        Identity("nobody", frozenset()),
        Identity(
            "expired",
            frozenset({"administration"}),
            global_scope=True,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ):
        with pytest.raises(AccessDenied):
            app.history.list(identity)


def test_report_viewer_cannot_download_invoice(app):
    artifact = app.invoices.generate(app.identities.current(), 1, "FAT-1", date.today(), date.today(), "mês")
    viewer = Identity("viewer", frozenset({"consultation"}), global_scope=True)
    with pytest.raises(AccessDenied):
        app.history.download(viewer, artifact.id)
    billing = Identity("billing", frozenset({"billing"}), global_scope=True)
    assert app.history.download(billing, artifact.id)[0].kind == "invoice"


@pytest.mark.parametrize("value", ["../secret", "/etc/passwd", "a" * 31, "A" * 32])
def test_artifact_traversal(app, value):
    with pytest.raises(ValidationError):
        app.history.store.read(value)


def test_artifacts_unique_integrity(app):
    store = app.history.store
    first = store.save(b"%PDF-1.7 a", "../name.pdf")
    second = store.save(b"%PDF-1.7 b", "../name.pdf")
    assert first.id != second.id and "/" not in first.filename
    app.repo.register_artifact(first, [1], "test")
    (store.root / f"{first.id}.pdf").write_bytes(b"modified")
    with pytest.raises(ValidationError):
        app.history.download(app.identities.current(), first.id)


def test_cron_contains_only_identifier(tmp_path):
    scheduler = CronScheduler(PurePosixPath("/opt/sar executable/launcher"))
    dangerous = Schedule(1, (1,), 5, "08:00", fatura_num_prefixo="'; touch /tmp/pwn; '")
    rendered = scheduler.render("0 1 * * * unrelated\n", [dangerous])
    assert "touch" not in rendered
    assert "unrelated" in rendered
    assert " 1 # SAR-REFACTORED [ID:1]" in rendered
    assert scheduler.render(rendered, [dangerous]) == rendered


def test_cron_read_failure_never_writes():
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        from types import SimpleNamespace

        return SimpleNamespace(returncode=1, stdout="", stderr="permission denied")

    with pytest.raises(IntegrationError):
        CronScheduler(Path("/opt/launcher"), run).synchronize([])
    assert calls == [["crontab", "-l"]]


def test_relay_headers_and_tls(tmp_path):
    settings = Settings(
        tmp_path,
        smtp_host="relay.example.org",
        mail_from="sar@example.org",
        mail_reply_to="team@example.org",
        mail_cc="gigafor@example.org",
    )
    relay = SMTPRelay(settings)
    msg, sender, recipients = relay.compose(
        Notification("client@example.org", "Assunto", "Corpo", (), "user@example.org")
    )
    assert msg["From"] == "sar@example.org"
    assert msg["Reply-To"] == "user@example.org"
    assert "gigafor@example.org" in recipients
    assert sender == "sar@example.org"
    with pytest.raises(ConfigurationError):
        SMTPRelay(replace(settings, smtp_tls="none")).compose(
            Notification("client@example.org", "a", "b", ())
        )


def test_smtp_uncertainty_and_tls_failure(tmp_path):
    settings = Settings(
        tmp_path,
        smtp_host="relay.example.org",
        mail_from="sar@example.org",
        mail_reply_to="team@example.org",
        mail_cc="gigafor@example.org",
    )

    class Transport:
        def __init__(self, *args, **kwargs):
            pass

        def ehlo(self):
            pass

        def starttls(self, context):
            assert context.check_hostname
            assert context.verify_mode != 0

        def send_message(self, *args, **kwargs):
            raise TimeoutError("SECRET")

        def close(self):
            pass

    with pytest.raises(DeliveryUncertain, match="indeterminado"):
        SMTPRelay(settings, Transport).send(Notification("client@example.org", "a", "b", ()))

    class BrokenTLS(Transport):
        def starttls(self, context):
            raise OSError("SECRET")

    with pytest.raises(IntegrationError, match="não submetida"):
        SMTPRelay(settings, BrokenTLS).send(Notification("client@example.org", "a", "b", ()))


def test_settings_reject_http(monkeypatch, tmp_path):
    monkeypatch.setenv("SAR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SAR_ZABBIX_URL", "http://example.org")
    with pytest.raises(ConfigurationError):
        Settings.from_env()


def test_unknown_errors_do_not_leak():
    from sar.security.redaction import public_error

    assert "TOPSECRET" not in public_error(RuntimeError("TOPSECRET"))
