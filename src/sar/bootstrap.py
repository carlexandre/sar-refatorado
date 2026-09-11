from dataclasses import dataclass
from sar.config.settings import Settings
from sar.domain.errors import ConfigurationError
from sar.security.identity import InternalTeamProvider
from sar.security.authorization import AuthorizationPolicy
from sar.infrastructure.persistence.sqlite import Database
from sar.infrastructure.persistence.repositories import Repository
from sar.infrastructure.storage.local_artifacts import LocalArtifacts
from sar.infrastructure.secrets.runtime_credentials import RuntimeCredentials
from sar.application.services.reports import Reports
from sar.application.services.invoices import Invoices
from sar.application.services.registrations import Registrations
from sar.application.services.history import History
from sar.application.services.schedules import Schedules
from sar.application.services.deliveries import Deliveries
from sar.application.services.invoice_templates import InvoiceTemplateService
from sar.security.authentication import (
    AuthenticationService, IdentityDirectory, PasswordHasher, UserAdministrationService,
)


@dataclass
class Application:
    settings: Settings
    repo: Repository
    identities: object
    policy: AuthorizationPolicy
    reports: Reports
    invoices: Invoices
    registrations: Registrations
    history: History
    schedules: Schedules
    deliveries: Deliveries
    monitoring: object
    templates: InvoiceTemplateService
    auth: object | None = None
    users: object | None = None

    def close(self):
        if hasattr(self.monitoring, "close"):
            self.monitoring.close()


def build(settings=None, *, monitoring=None, documents=None, notifications=None, identities=None):
    settings = settings or Settings.from_env()
    repo = Repository(Database(settings.database_path))
    auth = users = None
    if identities is None:
        if settings.access_mode == "internal_team":
            identities = InternalTeamProvider()
        elif settings.access_mode == "local":
            identities = IdentityDirectory(repo)
        else:
            raise ConfigurationError(
                "Acesso desabilitado. Configure SAR_ACCESS_MODE=local ou o perímetro internal_team."
            )
    policy = AuthorizationPolicy()
    if settings.access_mode == "local":
        hasher = PasswordHasher()
        auth = AuthenticationService(repo, identities, hasher)
        users = UserAdministrationService(repo, policy, hasher)
    store = LocalArtifacts(settings.artifact_dir)
    if monitoring is None:
        from sar.infrastructure.zabbix.client import ZabbixGateway

        monitoring = ZabbixGateway(settings, RuntimeCredentials(settings.credentials_dir))
    if documents is None:
        from sar.infrastructure.documents.renderer import Documents

        documents = Documents()
    if notifications is None:
        from sar.infrastructure.email.smtp_relay import SMTPRelay

        notifications = SMTPRelay(settings)
    reports = Reports(repo, monitoring, documents, store, policy)
    templates = InvoiceTemplateService(repo, policy)
    invoices = Invoices(
        repo, documents, store, policy, templates, settings.data_dir / "locks" / "invoice.lock"
    )
    registrations = Registrations(repo, monitoring, policy)
    history = History(repo, store, policy)
    schedules = Schedules(repo, policy)
    deliveries = Deliveries(repo, reports, invoices, history, notifications, identities, policy)
    return Application(
        settings,
        repo,
        identities,
        policy,
        reports,
        invoices,
        registrations,
        history,
        schedules,
        deliveries,
        monitoring,
        templates,
        auth,
        users,
    )
