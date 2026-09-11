from base64 import b64encode
from html import escape
from pathlib import Path
import streamlit as st

from sar.ui.components.common import navigate


ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "assets" / "ui"


MODULES = (
    (
        "Gerar Relatório",
        "Consulte o tráfego do Zabbix e exporte o documento PDF formatado.",
        "report.svg",
        "Gerar",
    ),
    (
        "Gerar Faturas",
        "Crie faturas comerciais personalizadas para as instituições vinculadas.",
        "invoice.svg",
        "Faturas",
    ),
    (
        "Gerenciar Instituições",
        "Gerencie as instituições, grupos, faturamento e interfaces de rede.",
        "institutions.svg",
        "Cadastros",
    ),
    (
        "Histórico",
        "Acesse o repositório de relatórios gerados anteriormente pelo sistema.",
        "history.svg",
        "Historico",
    ),
    (
        "Automação de E-mail",
        "Agende o envio mensal automático de relatórios e faturas por e-mail.",
        "automation.svg",
        "Automacao",
    ),
)

ADMIN_MODULE = (
    "Usuários e Acessos",
    "Gerencie contas, perfis e escopos de acesso.",
    "users.svg",
    "Administracao",
)


def _icon_data_uri(filename: str) -> str:
    encoded = b64encode((ICON_DIR / filename).read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _module_card(module):
    title, description, icon_file, page = module
    with st.container(border=True, key=f"sar_module_card_{page}"):
        st.html(
            '<div class="sar-module-card-content">'
            f'<img class="sar-module-icon" src="{_icon_data_uri(icon_file)}" alt="">'
            f"<h2>{escape(title)}</h2>"
            f"<p>{escape(description)}</p>"
            "</div>"
        )
        if st.button(
            title,
            key=f"open_module_{page}",
            width="stretch",
        ):
            navigate(page)


def _module_grid(modules, can_manage_users: bool):
    column_count = _module_column_count(can_manage_users)
    for start in range(0, len(modules), column_count):
        columns = st.columns(column_count, gap="medium")
        for column, module in zip(columns, modules[start:start + column_count], strict=False):
            with column:
                _module_card(module)


def _module_column_count(can_manage_users: bool) -> int:
    return 3 if can_manage_users else 5


def render(controller):
    st.html(
        """
        <div class="sar-page-intro">
            <div class="sar-eyebrow">Painel principal</div>
            <h1 class="sar-page-title">O que você deseja fazer?</h1>
            <p class="sar-page-description">Selecione um módulo para iniciar uma operação no SAR.</p>
        </div>
        """
    )
    actions = {
        "Gerar": "reports.read", "Faturas": "billing.ledger.read",
        "Cadastros": "registrations.read", "Historico": "reports.read",
        "Automacao": "schedules.read",
    }
    modules = [
        module for module in MODULES
        if controller.app.policy.allows(controller.identity, actions[module[3]])
    ]
    can_manage_users = (
        controller.app.users is not None
        and controller.app.policy.allows(controller.identity, "users.manage")
    )
    if can_manage_users:
        modules.append(ADMIN_MODULE)
    _module_grid(modules, can_manage_users)
