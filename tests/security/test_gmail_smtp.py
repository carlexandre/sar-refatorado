from dataclasses import replace
import smtplib
import pytest
from sar.config.settings import Settings
from sar.domain.errors import ConfigurationError, DeliveryUncertain, IntegrationError, ValidationError
from sar.domain.models import Notification
from sar.infrastructure.email.smtp_relay import SMTPRelay
from sar.infrastructure.secrets.runtime_credentials import RuntimeCredentials


PAIR = (("Fatura.pdf", b"%PDF-1.7 invoice"), ("Relatorio.pdf", b"%PDF-1.7 report"))


def notification(attachments=PAIR):
    return Notification("institution@example.org", "Instituição A", "Competência e vencimento", attachments,
                        "operator@example.org", "<stable@sar.invalid>")


class Secrets:
    def get(self, name):
        assert name == "gmail-app-password"
        return "synthetic-test-credential"


class Transport:
    def __init__(self, *args, **kwargs):
        assert args == ("smtp.gmail.com", 587)
        self.calls = ["connect"]
        self.esmtp_features = {"size": "35882577"}
        self.failure = None
        self.close_failure = False

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, context):
        assert context.check_hostname and context.verify_mode != 0
        self.calls.append("starttls")

    def login(self, username, password):
        assert username == "svc.popce@gmail.com"
        assert password == "synthetic-test-credential"
        self.calls.append("login")

    def send_message(self, msg, from_addr, to_addrs):
        assert from_addr == "svc.popce@gmail.com"
        assert to_addrs == ["svc.popce@rnp.br"]
        self.calls.append("send")
        if self.failure:
            raise self.failure
        return {}

    def close(self):
        self.calls.append("close")
        if self.close_failure:
            raise OSError("synthetic private diagnostic")


def test_fixed_headers_pair_and_message_id(tmp_path):
    msg, sender, recipients = SMTPRelay(Settings(tmp_path, mail_cc="old-copy@example.org",
                                             mail_reply_to="old-reply@example.org")).compose(notification())
    assert sender == msg["From"] == "svc.popce@gmail.com"
    assert recipients == ["svc.popce@rnp.br"] and msg["To"] == recipients[0]
    assert msg["Cc"] is None and msg["Bcc"] is None and msg["Reply-To"] is None
    assert msg["Subject"] == "Instituição A" and msg["Message-ID"] == "<stable@sar.invalid>"
    attachments = list(msg.iter_attachments())
    assert [part.get_content_type() for part in attachments] == ["application/pdf"] * 2
    assert [part.get_payload(decode=True) for part in attachments] == [content for _, content in PAIR]


@pytest.mark.parametrize("change", [dict(smtp_tls="none"), dict(smtp_port=465),
    dict(smtp_host="other.example.org"), dict(mail_from="other@example.org"),
    dict(smtp_user="other@example.org"), dict(mail_to="other@example.org")])
def test_fixed_configuration_cannot_be_overridden(tmp_path, change):
    with pytest.raises(ConfigurationError):
        SMTPRelay(replace(Settings(tmp_path), **change)).compose(notification())


@pytest.mark.parametrize("pair", [(), PAIR[:1], (PAIR[0], PAIR[0]),
    (("a.pdf", b"not a pdf"), PAIR[1]), (("a.txt", b"%PDF-1.7"), PAIR[1])])
def test_invalid_attachment_pair_is_blocked(tmp_path, pair):
    with pytest.raises(ValidationError):
        SMTPRelay(Settings(tmp_path)).compose(notification(pair))


def test_tls_then_authentication_then_submission(tmp_path):
    transport = Transport("smtp.gmail.com", 587)
    SMTPRelay(Settings(tmp_path), lambda *a, **k: transport, secrets=Secrets()).send(notification())
    assert transport.calls == ["connect", "ehlo", "starttls", "ehlo", "login", "send", "close"]


def test_missing_secret_never_connects(tmp_path):
    def factory(*args, **kwargs):
        pytest.fail("Must not connect without credential")
    with pytest.raises(ConfigurationError, match="gmail-app-password"):
        SMTPRelay(Settings(tmp_path), factory, secrets=RuntimeCredentials(None)).send(notification())


@pytest.mark.parametrize("stage", ["starttls", "login"])
def test_pre_submission_failure_is_safe_and_redacted(tmp_path, stage):
    transport = Transport("smtp.gmail.com", 587)
    def fail(*args, **kwargs):
        raise OSError("PRIVATE-DIAGNOSTIC")
    setattr(transport, stage, fail)
    with pytest.raises(IntegrationError, match="não submetida") as error:
        SMTPRelay(Settings(tmp_path), lambda *a, **k: transport, secrets=Secrets()).send(notification())
    assert "PRIVATE-DIAGNOSTIC" not in str(error.value) and "send" not in transport.calls


@pytest.mark.parametrize("failure, expected", [
    (TimeoutError("PRIVATE-DIAGNOSTIC"), DeliveryUncertain),
    (smtplib.SMTPServerDisconnected("PRIVATE-DIAGNOSTIC"), DeliveryUncertain),
    (smtplib.SMTPDataError(552, b"PRIVATE-DIAGNOSTIC"), IntegrationError),
    (smtplib.SMTPRecipientsRefused({"svc.popce@rnp.br": (550, b"PRIVATE")}), IntegrationError),
    (smtplib.SMTPSenderRefused(550, b"PRIVATE", "svc.popce@gmail.com"), IntegrationError),
])
def test_rejection_distinguished_from_ambiguous_submission(tmp_path, failure, expected):
    transport = Transport("smtp.gmail.com", 587)
    transport.failure = failure
    with pytest.raises(expected) as error:
        SMTPRelay(Settings(tmp_path), lambda *a, **k: transport, secrets=Secrets()).send(notification())
    assert "PRIVATE" not in str(error.value)


def test_close_failure_after_acceptance_is_success(tmp_path):
    transport = Transport("smtp.gmail.com", 587)
    transport.close_failure = True
    SMTPRelay(Settings(tmp_path), lambda *a, **k: transport, secrets=Secrets()).send(notification())


def test_oversize_message_keeps_pair_and_does_not_send(tmp_path):
    transport = Transport("smtp.gmail.com", 587)
    transport.esmtp_features = {"size": "100"}
    with pytest.raises(ValidationError, match="limite SMTP"):
        SMTPRelay(Settings(tmp_path), lambda *a, **k: transport, secrets=Secrets()).send(notification())
    assert "send" not in transport.calls and "login" not in transport.calls


def test_gmail_credential_allowlisted(tmp_path):
    path = tmp_path / "gmail-app-password"
    path.write_text("synthetic-test-credential", encoding="utf-8")
    path.chmod(0o600)
    assert RuntimeCredentials(tmp_path).get("gmail-app-password") == "synthetic-test-credential"


def test_password_env_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("SAR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SAR_SMTP_PASSWORD", "must-not-be-used")
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    with pytest.raises(ConfigurationError):
        SMTPRelay(Settings.from_env(), secrets=RuntimeCredentials(None)).send(notification())


def test_unreadable_credential_blocks_before_connection(tmp_path):
    class Unreadable:
        def get(self, name):
            raise OSError("PRIVATE-DIAGNOSTIC")
    def factory(*args, **kwargs):
        pytest.fail("Must not connect on credential error")
    with pytest.raises(ConfigurationError) as error:
        SMTPRelay(Settings(tmp_path), factory, secrets=Unreadable()).send(notification())
    assert "PRIVATE-DIAGNOSTIC" not in str(error.value)
