from email.message import EmailMessage
from email.utils import make_msgid
import smtplib
import ssl
from sar.domain.errors import ConfigurationError, DeliveryUncertain, IntegrationError
from sar.security.validation import email, text, filename


class SMTPRelay:
    def __init__(self, settings, smtp_factory=None):
        self.settings = settings
        self.smtp_factory = smtp_factory

    def compose(self, notification):
        settings = self.settings
        if not all((settings.smtp_host, settings.mail_from, settings.mail_reply_to, settings.mail_cc)):
            raise ConfigurationError("Relay, remetente, Reply-To e CC GigaFOR precisam ser configurados.")
        if settings.smtp_tls not in {"starttls", "implicit"} or not 1 <= settings.smtp_port <= 65535:
            raise ConfigurationError("Relay exige TLS e porta válida.")
        sender, recipient, copy = email(settings.mail_from), email(notification.to), email(settings.mail_cc)
        reply_to = email(notification.reply_to or settings.mail_reply_to)
        subject = text(notification.subject, "Assunto", required=True, limit=500)
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Reply-To"], msg["Subject"] = sender, recipient, reply_to, subject
        if copy.casefold() != recipient.casefold():
            msg["Cc"] = copy
        msg["Message-ID"] = notification.message_id or make_msgid(domain=sender.split("@")[1])
        msg.set_content(notification.body)
        for name, content in notification.attachments:
            msg.add_attachment(content, maintype="application", subtype="pdf", filename=filename(name))
        recipients = list({address.casefold(): address for address in (recipient, copy)}.values())
        return msg, sender, recipients

    def send(self, notification):
        msg, sender, recipients = self.compose(notification)
        context = ssl.create_default_context(cafile=self.settings.ca_bundle)
        transport = None
        submitting = False
        accepted = False
        try:
            if self.settings.smtp_tls == "implicit":
                factory = self.smtp_factory or smtplib.SMTP_SSL
                transport = factory(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.timeout,
                    context=context,
                )
            else:
                factory = self.smtp_factory or smtplib.SMTP
                transport = factory(
                    self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.timeout
                )
                transport.ehlo()
                transport.starttls(context=context)
                transport.ehlo()
            # No user login: the corporate relay authenticates the machine/network.
            submitting = True
            refused = transport.send_message(msg, from_addr=sender, to_addrs=recipients)
            if refused:
                raise DeliveryUncertain("Submissão parcial: revisar destinatários antes de reenviar.")
            accepted = True
        except DeliveryUncertain:
            raise
        except Exception:
            if submitting:
                raise DeliveryUncertain(
                    "Resultado da submissão SMTP indeterminado; reconciliação necessária."
                ) from None
            raise IntegrationError("Falha ao conectar ao relay com TLS; mensagem não submetida.") from None
        finally:
            if transport:
                try:
                    transport.close()
                except Exception:
                    # Closing after accepted DATA must never convert success into a retry.
                    if not accepted:
                        pass
