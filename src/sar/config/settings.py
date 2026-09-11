from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from sar.domain.errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    access_mode: str = "disabled"
    zabbix_url: str = ""
    ca_bundle: str | None = None
    credentials_dir: Path | None = None
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_tls: str = "starttls"
    mail_from: str = ""
    mail_reply_to: str = ""
    mail_cc: str = ""
    timezone: str = "America/Fortaleza"
    timeout: int = 30

    def __post_init__(self):
        if self.access_mode not in {"disabled", "internal_team", "local"}:
            raise ConfigurationError("Modo de acesso inválido.")
        if self.zabbix_url:
            parsed = urlparse(self.zabbix_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
                or parsed.query
            ):
                raise ConfigurationError("Zabbix exige URL HTTPS sem credenciais ou parâmetros embutidos.")
        if self.ca_bundle and not Path(self.ca_bundle).is_file():
            raise ConfigurationError("Arquivo de autoridades certificadoras não encontrado.")
        if self.timeout <= 0:
            raise ConfigurationError("Timeout deve ser positivo.")
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError):
            raise ConfigurationError("Fuso horário inválido.") from None

    @property
    def database_path(self) -> Path:
        return self.data_dir / "sar.db"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @classmethod
    def from_env(cls):
        root = os.environ.get("SAR_DATA_DIR")
        if not root:
            raise ConfigurationError("Configure SAR_DATA_DIR para um diretório de dados exclusivo.")
        try:
            settings = cls(
                data_dir=Path(root).resolve(),
                access_mode=os.getenv("SAR_ACCESS_MODE", "disabled"),
                zabbix_url=os.getenv("SAR_ZABBIX_URL", ""),
                ca_bundle=os.getenv("SAR_CA_BUNDLE") or None,
                credentials_dir=Path(os.environ["CREDENTIALS_DIRECTORY"])
                if os.getenv("CREDENTIALS_DIRECTORY")
                else None,
                smtp_host=os.getenv("SAR_SMTP_HOST", ""),
                smtp_port=int(os.getenv("SAR_SMTP_PORT", "587")),
                smtp_tls=os.getenv("SAR_SMTP_TLS", "starttls"),
                mail_from=os.getenv("SAR_MAIL_FROM", ""),
                mail_reply_to=os.getenv("SAR_MAIL_REPLY_TO", ""),
                mail_cc=os.getenv("SAR_MAIL_CC", ""),
                timezone=os.getenv("SAR_TIMEZONE", "America/Fortaleza"),
            )
            ZoneInfo(settings.timezone)
        except (ValueError, KeyError):
            raise ConfigurationError("Configuração de ambiente inválida.") from None
        if settings.ca_bundle and not Path(settings.ca_bundle).is_file():
            raise ConfigurationError("Arquivo de autoridades certificadoras não encontrado.")
        if settings.zabbix_url:
            parsed = urlparse(settings.zabbix_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ConfigurationError("Zabbix exige URL HTTPS sem credenciais embutidas.")
        return settings
