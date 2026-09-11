from pathlib import Path
import uuid
import pytest
from streamlit.testing.v1 import AppTest
import sar.ui.main
from sar.ui.views.home import _module_column_count
from sar.domain.models import AppUser
from sar.security.authentication import (
    AuthenticationService, IdentityDirectory, PasswordHasher, UserAdministrationService,
)


@pytest.mark.parametrize("module", [None, "Gerar Relatório", "Gerar Faturas", "Gerenciar Instituições", "Histórico", "Automação de E-mail"])
def test_pages_render_with_fake_integrations(app, monkeypatch, module):
    monkeypatch.setattr(sar.ui.main, "build", lambda: app)
    script = Path(__file__).resolve().parents[2] / "app.py"
    at = AppTest.from_file(str(script), default_timeout=20)
    at.run()
    if module:
        next(button for button in at.button if button.label == module).click().run()
    assert not at.exception
    assert not at.error


def test_manual_report_download(app, monkeypatch):
    monkeypatch.setattr(sar.ui.main, "build", lambda: app)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app.py"), default_timeout=20)
    at.run()
    next(button for button in at.button if button.label == "Gerar Relatório").click().run()
    # AppTest does not persist the hash selected by st.switch_page for callable pages.
    at._page_hash = next(
        page_hash
        for page_hash, data in at._registered_pages.items()
        if data.get("url_pathname") == "gerar"
    )
    at.multiselect[0].set_value([1]).run()
    next(button for button in at.button if button.label == "Gerar Relatório e Salvar").click().run()
    assert not at.exception
    assert not at.error
    assert app.repo.history()


def test_back_button_navigates_in_the_current_page(app, monkeypatch):
    monkeypatch.setattr(sar.ui.main, "build", lambda: app)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app.py"), default_timeout=20)
    at.run()
    next(button for button in at.button if button.label == "Gerar Relatório").click().run()

    next(button for button in at.button if button.label == "Voltar ao início").click().run()

    assert any(button.label == "Gerar Relatório" for button in at.button)
    assert not at.exception


def test_theme_selector_persists_choice_in_session_across_navigation(app, monkeypatch):
    monkeypatch.setattr(sar.ui.main, "build", lambda: app)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app.py"), default_timeout=20)
    at.run()

    at.segmented_control[0].set_value("light").run()

    next(button for button in at.button if button.label == "Gerar Relatório").click().run()

    assert at.session_state["sar_color_theme"] == "light"
    assert at.session_state["sar_theme_selector"] == "light"
    assert "theme" not in at.query_params
    assert not at.exception


def test_local_login_gates_the_streamlit_application(app, monkeypatch):
    hasher = PasswordHasher()
    user = AppUser(
        uuid.uuid4().hex, "admin", "Administrador", "admin@example.org",
        password_hash=hasher.hash("correct horse battery staple"),
        must_change_password=False, global_scope=True,
    )
    app.repo.create_user(user, {"administration"})
    directory = IdentityDirectory(app.repo)
    app.identities = directory
    app.auth = AuthenticationService(app.repo, directory, hasher)
    app.users = UserAdministrationService(app.repo, app.policy, hasher)
    monkeypatch.setattr(sar.ui.main, "build", lambda: app)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app.py"), default_timeout=20)
    at.run()
    assert [item.label for item in at.text_input[:2]] == ["Usuário", "Senha"]
    at.text_input[0].set_value("admin")
    at.text_input[1].set_value("correct horse battery staple")
    next(button for button in at.button if button.label == "Entrar").click().run()
    assert not at.exception
    assert not at.error
    assert any(button.label == "Sair" for button in at.button)
    assert len(at.get("popover")) == 1

    next(button for button in at.button if button.label == "Gerar Relatório").click().run()

    assert not any(item.label in {"Usuário", "Senha"} for item in at.text_input)
    assert len(at.get("popover")) == 1
    assert not at.exception


def test_home_grid_uses_three_columns_for_user_admin_and_five_for_other_roles():
    assert _module_column_count(can_manage_users=True) == 3
    assert _module_column_count(can_manage_users=False) == 5
