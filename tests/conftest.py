import pytest
from sar.bootstrap import build
from sar.config.settings import Settings
from sar.domain.models import Group, Institution, CommercialProfile, InvoiceItem
from sar.infrastructure.persistence.sqlite import initialize


class Monitoring:
    def hosts(self):
        return [{"hostid": "10", "name": "RG1 - Instituição -- GIGAFOR"}]

    def items(self, host_id):
        return [{"itemid": "11", "name": "Interface entrada"}, {"itemid": "12", "name": "Interface saída"}]

    def history(self, item_id, start, end):
        return [
            {"clock": str(start), "value": "100000000"},
            {"clock": str(start + 3600), "value": "200000000"},
        ]

    def trends(self, item_id, start, end):
        return []

    def events(self, host_id, start, end):
        return [{"eventid": "1", "name": "Bandwidth high", "clock": str(start), "r_eventid": "2"}]

    def recoveries(self, ids):
        return []


class Documents:
    def report(self, data, period):
        return b"%PDF-1.7\nsynthetic report"

    def invoice(self, data, template=None):
        return b"%PDF-1.7\nsynthetic invoice"


class Notifications:
    def __init__(self):
        self.messages = []

    def send(self, notification):
        self.messages.append(notification)


@pytest.fixture
def app(tmp_path):
    settings = Settings(tmp_path, access_mode="internal_team")
    initialize(settings.database_path)
    app = build(settings, monitoring=Monitoring(), documents=Documents(), notifications=Notifications())
    group_id = app.repo.save_group(Group(0, "Grupo", email_contato="grupo@example.org", fatura_para="Grupo"))
    for name in ("Instituição A", "Instituição B", "Instituição C", "Instituição D"):
        link_id = app.repo.save_institution(
            Institution(0, group_id, name, "10", "11", "12", "1 Gbps", "cliente@example.org")
        )
        app.repo.save_profiles([CommercialProfile(link_id, name)], [InvoiceItem("Conectividade", 1, 12.50)])
        app.invoices.save_sequence(app.identities.current(), link_id, 1)
    app.repo.save_items(group_id, [InvoiceItem("Grupo exclusivo", 1, 100.0)], True)
    app.invoices.save_sequence(app.identities.current(), group_id, 1, group=True)
    yield app
    app.close()
