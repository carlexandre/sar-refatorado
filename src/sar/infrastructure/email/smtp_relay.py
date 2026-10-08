from email.message import EmailMessage
from email.policy import SMTP
from email.utils import make_msgid
import smtplib
import ssl
from sar.domain.errors import ConfigurationError, DeliveryUncertain, IntegrationError, ValidationError
from sar.security.validation import email, text, filename


class SMTPRelay:
    """Authenticated Gmail submission; a successful return means SMTP acceptance only."""

    def __init__(self, settings, smtp_factory=None, *, secrets=None):
        self.settings = settings
        self.smtp_factory = smtp_factory
        self.secrets = secrets

    def compose(self, notification):
        settings = self.settings
        if (settings.smtp_host, settings.smtp_port, settings.smtp_tls,
                settings.smtp_user, settings.mail_from, settings.mail_to) != (
                "smtp.gmail.com", 587, "starttls",
                "svc.popce@gmail.com", "svc.popce@gmail.com", "svc.popce@rnp.br"):
            raise ConfigurationError("Configure Gmail SMTP 587/STARTTLS e os endereços fixos do SAR.")
        sender, recipient = email(settings.mail_from), email(settings.mail_to)
        if len(notification.attachments) != 2:
            raise ValidationError("Envio exige fatura e relatório em PDF juntos.")
        msg = EmailMessage(policy=SMTP)
        msg["From"], msg["To"], msg["Subject"] = (
            sender, recipient, text(notification.subject, "Assunto", required=True, limit=500)
        )
        msg["Message-ID"] = notification.message_id or make_msgid(domain=sender.split("@")[1])
        msg.set_content(notification.body)
        names = set()
        for name, content in notification.attachments:
            safe_name = filename(name)
            if (not safe_name.lower().endswith(".pdf") or safe_name in names
                    or not content.startswith(b"%PDF-")):
                raise ValidationError("Anexos devem ser dois PDFs válidos com nomes distintos.")
            names.add(safe_name)
            msg.add_attachment(content, maintype="application", subtype="pdf", filename=safe_name)
        return msg, sender, [recipient]

    def send(self, notification):
        msg, sender, recipients = self.compose(notification)
        try:
            password = self.secrets.get("gmail-app-password") if self.secrets else None
            context = ssl.create_default_context()
            if self.settings.ca_bundle:
                context.load_verify_locations(cafile=self.settings.ca_bundle)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("Falha ao carregar credencial ou CA SMTP; mensagem não submetida.") from None
        if not password:
            raise ConfigurationError("Credencial systemd gmail-app-password não disponível; mensagem não submetida.")
        transport = None
        submitting = False
        try:
            factory = self.smtp_factory or smtplib.SMTP
            transport = factory(self.settings.smtp_host, self.settings.smtp_port,
                                timeout=self.settings.timeout)
            transport.ehlo()
            transport.starttls(context=context)
            transport.ehlo()
            limit = transport.esmtp_features.get("size", "")
            if limit.isdigit() and len(msg.as_bytes()) > int(limit):
                raise ValidationError("Fatura e relatório excedem o limite SMTP; envio bloqueado sem separar anexos.")
            transport.login(self.settings.smtp_user, password)
            submitting = True
            refused = transport.send_message(msg, from_addr=sender, to_addrs=recipients)
            if refused:
                raise IntegrationError("Gmail recusou o destinatário; mensagem não submetida.")
        except (ConfigurationError, ValidationError, IntegrationError):
            raise
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            raise IntegrationError("Gmail recusou a submissão SMTP; mensagem não aceita.") from None
        except Exception:
            if submitting:
                raise DeliveryUncertain(
                    "Resultado da submissão SMTP indeterminado; reconciliação necessária."
                ) from None
            raise IntegrationError("Falha na conexão TLS ou autenticação Gmail; mensagem não submetida.") from None
        finally:
            password = None
            if transport:
                try:
                    transport.close()
                except Exception:
                    # DATA acceptance remains successful even when closing the socket fails.
                    pass
