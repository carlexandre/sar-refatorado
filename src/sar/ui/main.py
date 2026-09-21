import json

import streamlit as st
from sar.bootstrap import build
from sar.security.redaction import public_error
from sar.ui.controllers.context import Controller
from sar.ui.theme import apply_theme, render_theme_selector


_SESSION_COOKIE = "sar_session_token"


def _write_session_cookie(token, *, reload_page=False):
    """Share a validated server-side session with other browser tabs."""
    value = token or ""
    max_age = 8 * 60 * 60 if token else 0
    cookie = f"{_SESSION_COOKIE}={value}; Path=/; Secure; SameSite=Strict; Max-Age={max_age}"
    reload_script = "window.location.reload();" if reload_page else ""
    st.html(f"<script>document.cookie = {json.dumps(cookie)};{reload_script}</script>",
            unsafe_allow_javascript=True)


def _render_profile_menu(app, user, identity, token):
    """Keep account context and logout available without leaving the current page."""
    username = user.username if user is not None else identity.subject
    display_name = user.display_name if user is not None else "Sessão interna"
    with st.popover(
        f"@{username}",
        icon=":material/account_circle:",
        key="sar_profile_menu",
        help=f"Conta conectada: {display_name}",
    ):
        st.markdown(f"**{display_name}**")
        st.caption(f"Usuário: @{username}")
        if user is not None and user.email:
            st.caption(f"E-mail: {user.email}")
        roles = ", ".join(sorted(identity.roles)) or "sem perfil"
        st.caption(f"Perfis: {roles}")
        if identity.global_scope:
            st.caption("Escopo: global")
        else:
            scopes = []
            if identity.group_ids:
                scopes.append(f"{len(identity.group_ids)} grupo(s)")
            if identity.institution_ids:
                scopes.append(f"{len(identity.institution_ids)} instituição(ões)")
            st.caption(f"Escopo: {', '.join(scopes) if scopes else 'restrito'}")
        st.divider()
        render_theme_selector()
        if app.auth is not None:
            st.divider()
            if st.button("Sair", key="sar_logout", icon=":material/logout:", width="stretch"):
                app.auth.logout(token)
                st.session_state.pop("sar_session_token", None)
                _write_session_cookie(None, reload_page=True)


def main():
    st.set_page_config(page_title="SAR | PoP-CE", layout="wide", page_icon=":material/monitoring:")
    apply_theme()
    app = None
    try:
        app = build()
        if app.auth is not None:
            token = st.session_state.get("sar_session_token") or st.context.cookies.get(_SESSION_COOKIE)
            try:
                identity = app.auth.current(token)
            except Exception:
                identity = None
            if identity is None:
                if st.context.cookies.get(_SESSION_COOKIE):
                    _write_session_cookie(None)
                st.markdown("## Entrar no SAR")
                with st.form("sar_login"):
                    username = st.text_input("Usuário")
                    password = st.text_input("Senha", type="password")
                    submitted = st.form_submit_button("Entrar", type="primary")
                if submitted:
                    try:
                        token = app.auth.login(username, password)
                        st.session_state["sar_session_token"] = token
                        _write_session_cookie(token, reload_page=True)
                        st.success("Login realizado. Abrindo o SAR...")
                    except Exception as error:
                        st.error(public_error(error))
                return
            st.session_state["sar_session_token"] = token
            _write_session_cookie(token)
            user = app.repo.user(identity.subject)
            if user.must_change_password:
                st.markdown("## Altere sua senha temporária")
                with st.form("sar_change_password"):
                    current_password = st.text_input("Senha atual", type="password")
                    new_password = st.text_input("Nova senha", type="password")
                    confirmation = st.text_input("Confirme a nova senha", type="password")
                    submitted = st.form_submit_button("Alterar senha", type="primary")
                if submitted:
                    if new_password != confirmation:
                        st.error("As novas senhas não coincidem.")
                    else:
                        try:
                            app.auth.change_password(token, current_password, new_password)
                            st.session_state.pop("sar_session_token", None)
                            _write_session_cookie(None, reload_page=True)
                            st.success("Senha alterada. Entre novamente.")
                        except Exception as error:
                            st.error(public_error(error))
                return
        else:
            identity = app.identities.current()
            user = None
            token = None
        controller = Controller(app, identity)
        from sar.ui.views import home, reports, invoices, registrations, history, automation, users

        route_specs = {
            "Home": (home, "Início", None, ":material/home:", "reports.read"),
            "Gerar": (reports, "Gerar Relatório", "gerar", ":material/monitoring:", "reports.read"),
            "Faturas": (invoices, "Faturas", "faturas", ":material/receipt_long:", "billing.ledger.read"),
            "Cadastros": (
                registrations, "Cadastros", "cadastros", ":material/account_balance:",
                "registrations.read",
            ),
            "Historico": (history, "Histórico", "historico", ":material/folder:", "reports.read"),
            "Automacao": (
                automation, "Automação", "automacao", ":material/smart_toy:", "schedules.read",
            ),
        }
        if app.users is not None and app.policy.allows(identity, "users.manage"):
            route_specs["Administracao"] = (
                users, "Usuários e Acessos", "administracao", ":material/manage_accounts:", "users.manage",
            )
        pages = {}
        for name, (view, title, path, icon, permission) in route_specs.items():
            if name != "Home" and not app.policy.allows(identity, permission):
                continue
            options = {"title": title, "icon": icon, "default": name == "Home"}
            if path is not None:
                options["url_path"] = path
            pages[name] = st.Page(lambda view=view: view.render(controller), **options)
        controller.pages = pages
        st.session_state["sar_navigation_pages"] = pages
        selected_page = st.navigation(list(pages.values()), position="hidden")
        _render_profile_menu(app, user, identity, token)
        selected_page.run()
    except Exception as error:
        st.error(public_error(error))
    finally:
        if app:
            app.close()


if __name__ == "__main__":
    main()
