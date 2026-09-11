from dataclasses import replace
from html import escape
import streamlit as st
from sar.domain.models import Group, Institution, CommercialProfile
from sar.domain.billing import total, currency
from sar.application.services.registrations import clean_host_name
from sar.ui.components.common import heading, action, item_editor, commercial_fields


def saved(callback):
    result = action(callback)
    if result is not None:
        st.success("Dados salvos.")
    return result


def render(controller):
    heading("Gestão de Grupos, Instituições e Faturas")
    groups = controller.call("registrations", "groups")
    institutions = controller.call("registrations", "institutions")
    labels = {g.id: g.nome for g in groups}
    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### 1. Criar Grupo")
        with st.form("create_group"):
            name = st.text_input("Nome do Grupo (ex: GigaFOR, CDC)")
            parent = st.selectbox(
                "Subgrupo de (Opcional):",
                [None] + [g.id for g in groups if g.parent_id is None],
                format_func=lambda key: labels.get(key, "Nenhum (Criar como Grupo Raiz)"),
            )
            if st.form_submit_button("Salvar Grupo"):
                if saved(lambda: controller.call("registrations", "save_group", Group(0, name, parent))):
                    st.rerun()
        st.markdown("#### Grupos Atuais")
        for group in groups:
            with st.expander(
                (labels.get(group.parent_id, "") + " ↳ " if group.parent_id else "") + group.nome
            ):
                new_name = st.text_input("Novo nome", group.nome, key=f"name_{group.id}")
                with st.container(horizontal=True, gap="small", wrap=False):
                    save_group_clicked = st.button(
                        "Salvar",
                        key=f"rename_{group.id}",
                        icon=":material/save:",
                        use_container_width=True,
                    )
                    delete_group_clicked = st.button(
                        "Excluir",
                        key=f"delete_group_{group.id}",
                        icon=":material/delete:",
                        use_container_width=True,
                    )
                if save_group_clicked and saved(
                    lambda: controller.call("registrations", "save_group", replace(group, nome=new_name))
                ):
                    st.rerun()
                if delete_group_clicked:

                    def delete_group():
                        controller.call("registrations", "delete_group", group.id)
                        return True

                    if action(delete_group):
                        st.rerun()
                group_institutions = [
                    institution.nome_instituicao
                    for institution in institutions
                    if institution.grupo_id == group.id
                ]
                if group_institutions:
                    items = "".join(f"<li>{escape(name)}</li>" for name in group_institutions)
                    st.html(f'<ul class="sar-institution-list">{items}</ul>')
    with right:
        st.markdown("#### 2. Instituições")
        add, edit, billing = st.tabs(["Adicionar Nova", "Editar", "Perfis de Fatura"])
        with add:
            institution_form(controller, groups, None, "add")
        with edit:
            if institutions:
                names = {
                    i.id: f"{labels.get(i.grupo_id, 'Sem Grupo')} - {i.nome_instituicao}"
                    for i in institutions
                }
                chosen = st.selectbox(
                    "Selecione a Instituição para Editar:", list(names), format_func=names.get
                )
                institution_form(
                    controller, groups, next(i for i in institutions if i.id == chosen), f"edit_{chosen}"
                )
            else:
                st.info("Nenhuma Instituição cadastrada para editar.")
        with billing:
            billing_forms(controller, groups, institutions)


def institution_form(controller, groups, current, key):
    if not groups:
        st.info("Crie um grupo primeiro.")
        return
    group_labels = {g.id: g.nome for g in groups}
    group_keys = list(group_labels)
    group_id = st.selectbox(
        "Grupo:",
        group_keys,
        format_func=group_labels.get,
        index=group_keys.index(current.grupo_id) if current and current.grupo_id in group_keys else 0,
        key=f"{key}_group",
    )
    hosts = action(lambda: controller.call("registrations", "hosts"))
    if not hosts:
        st.info("Nenhum host disponível no Zabbix.")
        return
    host_labels = {h["hostid"]: h["name"] for h in hosts}
    host_keys = list(host_labels)
    if current and current.host_id not in host_labels:
        st.warning("Host vinculado não está disponível no inventário atual.")
        return
    host_id = st.selectbox(
        "Host no Zabbix:",
        host_keys,
        format_func=host_labels.get,
        index=host_keys.index(current.host_id) if current else 0,
        disabled=bool(current),
        key=f"{key}_host",
    )
    interfaces = action(lambda: controller.call("registrations", "interfaces", host_id))
    if not interfaces:
        st.warning("Nenhuma interface encontrada neste host.")
        return
    items = {i["itemid"]: i["name"] for i in interfaces}
    keys = list(items)
    with st.form(f"{key}_form"):
        name = st.text_input(
            "Nome da Instituição:",
            value=current.nome_instituicao if current else clean_host_name(host_labels[host_id]),
        )
        email = st.text_input("E-mail de Contato (Opcional):", value=current.email_contato if current else "")
        down = st.selectbox(
            "Interface de DOWNLOAD (Entrada):",
            keys,
            format_func=items.get,
            index=keys.index(current.item_down_id) if current and current.item_down_id in keys else 0,
        )
        up = st.selectbox(
            "Interface de UPLOAD (Saída):",
            keys,
            format_func=items.get,
            index=keys.index(current.item_up_id) if current and current.item_up_id in keys else 0,
        )
        capacity = st.text_input(
            "Capacidade (ex: 1 Gbps, 500 Mbps) *Obrigatório*", value=current.capacidade_str if current else ""
        )
        if current:
            with st.container(horizontal=True, gap="small", wrap=False):
                save_institution_clicked = st.form_submit_button(
                    "Salvar Alterações",
                    type="primary",
                    icon=":material/save:",
                    use_container_width=True,
                )
                delete_institution_clicked = st.form_submit_button(
                    "Excluir Instituição",
                    icon=":material/delete:",
                    use_container_width=True,
                )
        else:
            save_institution_clicked = st.form_submit_button(
                "Salvar Instituição",
                type="primary",
                icon=":material/save:",
                use_container_width=True,
            )
            delete_institution_clicked = False
        if save_institution_clicked:
            value = Institution(
                current.id if current else 0,
                group_id,
                name or clean_host_name(host_labels[host_id]),
                host_id,
                down,
                up,
                capacity,
                email,
            )
            if saved(lambda: controller.call("registrations", "save_institution", value)):
                st.rerun()
        if delete_institution_clicked:

            def delete():
                controller.call("registrations", "delete_institution", current.id)
                return True

            if action(delete):
                st.rerun()


def billing_forms(controller, groups, institutions):
    st.markdown("#### Perfil de Fatura por Grupo")
    if groups:
        choices = {g.id: g.nome for g in groups}
        target = st.selectbox("Selecione o Grupo:", list(choices), format_func=choices.get)
        group = next(g for g in groups if g.id == target)
        fields = commercial_fields(group, f"group_billing_{target}")
        email = st.text_input(
            "E-mail de Contato (Para automação):", group.email_contato, key=f"group_email_{target}"
        )
        st.markdown("#### Itens da Fatura do Grupo")
        st.caption("Itens exclusivos do grupo, independentes das instituições vinculadas.")
        items = item_editor(
            controller.call("registrations", "items", target, group=True), f"group_items_{target}"
        )
        st.write(f"Total Calculado da Fatura: {currency(total(items))}")
        with st.container(horizontal=True, gap="small", wrap=False):
            save_profile_clicked = st.button(
                "Salvar Perfil do Grupo",
                type="primary",
                icon=":material/save:",
                use_container_width=True,
            )
            save_items_clicked = st.button(
                "Salvar Itens do Grupo",
                type="primary",
                icon=":material/playlist_add_check:",
                use_container_width=True,
            )
        if save_profile_clicked:

            def save():
                controller.call(
                    "registrations",
                    "save_group_billing",
                    replace(group, email_contato=email, **fields),
                )
                return True

            saved(save)
        if save_items_clicked:

            def save_items():
                controller.call("registrations", "save_group_items", target, items)
                return True

            saved(save_items)
    st.divider()
    st.markdown("#### Perfil de Fatura Individual (Instituição)")
    choices = {i.id: i.nome_instituicao for i in institutions}
    selected = st.multiselect("Selecione a(s) Instituição(ões):", list(choices), format_func=choices.get)
    if not selected:
        st.info("Selecione uma ou mais instituições acima para configurar.")
        return
    key = "individual_" + "_".join(str(i) for i in selected)
    profile = controller.call("registrations", "profile", selected[0]) or CommercialProfile(selected[0], "")
    fields = commercial_fields(profile, key)
    current_items = controller.call("registrations", "items", selected[0]) if len(selected) == 1 else []
    items = item_editor(current_items, key + "_items")
    st.write(f"Total Calculado da Fatura: {currency(total(items))}")
    if st.button("Salvar Perfil Comercial", type="primary"):

        def save():
            controller.call(
                "registrations", "save_profiles", [CommercialProfile(i, **fields) for i in selected], items
            )
            return True

        saved(save)
