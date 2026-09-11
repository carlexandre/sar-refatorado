import streamlit as st

from sar.ui.components.common import action, data_table, heading


ROLES = ["consultation", "operations", "billing", "administration"]


def render(controller):
    heading("Usuários e Acessos")
    groups = controller.call("registrations", "groups")
    institutions = controller.call("registrations", "institutions")
    group_labels = {item.id: item.nome for item in groups}
    link_labels = {item.id: item.nome_instituicao for item in institutions}
    create, manage, audit = st.tabs(["Criar usuário", "Gerenciar", "Auditoria"])
    with create:
        with st.form("create_user"):
            username = st.text_input("Usuário")
            display_name = st.text_input("Nome de exibição")
            email = st.text_input("E-mail")
            roles = st.multiselect("Perfis", ROLES)
            global_scope = st.checkbox("Escopo global")
            group_ids = st.multiselect("Grupos permitidos", list(group_labels), format_func=group_labels.get)
            link_ids = st.multiselect("Instituições permitidas", list(link_labels), format_func=link_labels.get)
            submitted = st.form_submit_button("Criar usuário", type="primary")
        if submitted:
            result = action(lambda: controller.call(
                "users", "create", username, display_name, email, roles, global_scope, group_ids, link_ids
            ))
            if result:
                _, temporary = result
                st.session_state["temporary_password"] = temporary
        if temporary := st.session_state.pop("temporary_password", None):
            st.success("Usuário criado. Copie a senha temporária agora; ela não será exibida novamente.")
            st.code(temporary)
    with manage:
        records = controller.call("users", "list")
        for record in records:
            user = record["user"]
            with st.expander(f"{user.username} — {user.display_name}"):
                with st.form(f"user_{user.id}"):
                    name = st.text_input("Nome", user.display_name, key=f"name_{user.id}")
                    email = st.text_input("E-mail", user.email or "", key=f"email_{user.id}")
                    active = st.checkbox("Ativo", bool(user.is_active), key=f"active_{user.id}")
                    global_scope = st.checkbox("Escopo global", bool(user.global_scope), key=f"global_{user.id}")
                    roles = st.multiselect("Perfis", ROLES, default=list(record["roles"]), key=f"roles_{user.id}")
                    group_ids = st.multiselect(
                        "Grupos", list(group_labels), default=list(record["groups"]),
                        format_func=group_labels.get, key=f"groups_{user.id}",
                    )
                    link_ids = st.multiselect(
                        "Instituições", list(link_labels), default=list(record["institutions"]),
                        format_func=link_labels.get, key=f"links_{user.id}",
                    )
                    save = st.form_submit_button("Salvar")
                if save and action(lambda: controller.call(
                    "users", "save", user.id, name, email, active, global_scope, roles, group_ids, link_ids
                )) is not None:
                    st.success("Acessos atualizados; sessões anteriores foram revogadas.")
                    st.rerun()
                if st.button("Redefinir senha", key=f"reset_{user.id}"):
                    temporary = action(lambda: controller.call("users", "reset_password", user.id))
                    if temporary:
                        st.warning("Copie a senha temporária agora.")
                        st.code(temporary)
    with audit:
        data_table(controller.app.repo.audit_recent(), "Nenhum evento de auditoria registrado.")
