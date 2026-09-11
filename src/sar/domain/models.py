from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @property
    def text(self) -> str:
        return f"{self.start:%d/%m/%Y} a {self.end:%d/%m/%Y}"


@dataclass(frozen=True)
class Group:
    id: int
    nome: str
    parent_id: int | None = None
    email_contato: str = ""
    fatura_para: str = ""
    cnpj: str = ""
    cep: str = ""
    endereco: str = ""
    numero: str = ""
    cidade: str = ""
    uf: str = ""


@dataclass(frozen=True)
class Institution:
    id: int
    grupo_id: int
    nome_instituicao: str
    host_id: str
    item_down_id: str
    item_up_id: str
    capacidade_str: str
    email_contato: str = ""


@dataclass(frozen=True)
class CommercialProfile:
    link_id: int
    fatura_para: str
    cnpj: str = ""
    cep: str = ""
    endereco: str = ""
    numero: str = ""
    cidade: str = ""
    uf: str = ""
    email_contato: str = ""


@dataclass(frozen=True)
class InvoiceItem:
    descricao: str
    quantidade: int
    valor_unitario: float


@dataclass(frozen=True)
class Schedule:
    id: int
    link_ids: tuple[int, ...]
    dia_envio: int
    horario: str
    incluir_fatura: bool = True
    fatura_num_prefixo: str = "FAT"
    fatura_venc_dia: int = 15
    ativo: bool = True
    periodo_modo: str = "mes_anterior"
    data_inicio: str | None = None
    data_fim: str | None = None
    grupo_id: int | None = None
    owner_id: str = "internal-team"


@dataclass(frozen=True)
class ReportData:
    link_id: int
    infos: dict[str, str]
    stats: dict[str, float]
    alerts: list[dict[str, str]]
    series: list[dict[str, Any]]


@dataclass(frozen=True)
class Artifact:
    id: str
    filename: str
    sha256: str
    size: int
    template_version: str = "legacy_v1"
    kind: str = "report"


@dataclass(frozen=True)
class ReportResult:
    artifact: Artifact
    included_ids: tuple[int, ...]
    skipped_ids: tuple[int, ...]


@dataclass(frozen=True)
class Notification:
    to: str
    subject: str
    body: str
    attachments: tuple[tuple[str, bytes], ...]
    reply_to: str | None = None
    message_id: str | None = None


@dataclass
class ExecutionResult:
    id: str
    status: str
    artifacts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AppUser:
    id: str
    username: str
    display_name: str
    email: str | None = None
    auth_provider: str = "local"
    external_subject: str | None = None
    password_hash: str | None = None
    is_active: bool = True
    must_change_password: bool = True
    global_scope: bool = False
    failed_attempts: int = 0
    locked_until: str | None = None
    last_login_at: str | None = None
    password_changed_at: str | None = None


@dataclass(frozen=True)
class InvoiceTemplateOverride:
    id: int = 0
    group_id: int | None = None
    link_id: int | None = None
    base_version: str | None = None
    title_text: str | None = None
    payment_terms: str | None = None
    observation_mode: str = "inherit"
    observation_text: str | None = None
    logo_asset: str | None = None
    primary_color: str | None = None
    border_color: str | None = None
    text_color: str | None = None
    font_family: str | None = None
    title_font_size: int | None = None
    body_font_size: int | None = None
    show_period: bool | None = None
    revision: int = 1
    updated_by: str = ""


@dataclass(frozen=True)
class ResolvedInvoiceTemplate:
    base_version: str = "legacy_v1"
    title_text: str = "CONECTIVIDADE A REDE GIGAFOR"
    payment_terms: str = ""
    observation_text: str = ""
    show_observation: bool = False
    logo_asset: str = "gigafor-logo.png"
    primary_color: str = "#000000"
    border_color: str = "#000000"
    text_color: str = "#000000"
    font_family: str = "Arial"
    title_font_size: int = 22
    body_font_size: int = 9
    show_period: bool = True


@dataclass(frozen=True)
class InvoiceSequence:
    id: int
    group_id: int | None
    link_id: int | None
    initial_value: int
    next_value: int
    prefix: str = "FAT"
    padding: int = 0
    revision: int = 1
    updated_by: str = ""
