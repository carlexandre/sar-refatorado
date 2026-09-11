from datetime import date, timedelta
import uuid

import streamlit as st

from sar.domain.models import InvoiceTemplateOverride
from sar.domain.periods import reference
from sar.ui.components.common import action, data_table, download, heading


def _targets(controller):
    institutions = controller.call("registrations", "institutions")
    groups = controller.call("registrations", "groups")
    profiles = {item.id: controller.call("registrations", "profile", item.id) for item in institutions}
    targets = {
        f"link:{item.id}": (item.id, False, item.nome_instituicao)
        for item in institutions if profiles[item.id]
    }
    targets.update({
        f"group:{item.id}": (item.id, True, f"Grupo: {item.nome}")
        for item in groups if item.fatura_para
    })
    return institutions, groups, targets


def render(controller):
    heading("Faturas Comerciais")
    institutions, groups, targets = _targets(controller)
    emit, templates, sequences, ledger = st.tabs(["Emitir", "Templates", "Sequências", "Livro de Emissões"])
    with emit:
        _emit(controller, targets)
    with templates:
        _templates(controller, institutions, groups)
    with sequences:
        _sequences(controller, targets)
    with ledger:
        _ledger(controller)


def _emit(controller, targets):
    if not targets:
        st.info("Cadastre um perfil comercial antes de emitir uma fatura.")
        return
    selected = st.selectbox("Cliente:", list(targets), format_func=lambda key: targets[key][2])
    target_id, group, label = targets[selected]
    sequence = controller.call("invoices", "sequence", target_id, group=group)
    if sequence:
        numeric = str(sequence.next_value).zfill(sequence.padding)
        predicted = f"{sequence.prefix}-{numeric}" if sequence.prefix else numeric
        st.info(f"Próximo número previsto: {predicted}")
    else:
        st.warning("Este alvo ainda não possui sequência configurada.")
    a, b = st.columns(2)
    issued = a.date_input("Data da Fatura", value=date.today())
    due = b.date_input("Data de Vencimento", value=date.today() + timedelta(days=15))
    mode = st.radio("Período demonstrado:", ["Mês anterior completo", "Período personalizado"])
    start = end = None
    if mode == "Período personalizado":
        a, b = st.columns(2)
        start = a.date_input("Data Início", value=date.today() - timedelta(days=30)).isoformat()
        end = b.date_input("Data Fim", value=date.today()).isoformat()
    _, description = reference(date.today(), start, end)
    selection = (selected, issued.isoformat(), due.isoformat(), start, end)
    if st.session_state.get("invoice_issue_selection") != selection:
        st.session_state["invoice_issue_selection"] = selection
        st.session_state["invoice_issue_key"] = uuid.uuid4().hex
        st.session_state.pop("invoice_result", None)
    left, right = st.columns(2)
    if left.button("Gerar prévia", use_container_width=True):
        content = action(lambda: controller.call(
            "invoices", "preview", target_id, issued, due, description, group=group
        ))
        if content:
            st.session_state["invoice_preview"] = (selection, content)
    if right.button("Emitir fatura", type="primary", disabled=sequence is None, use_container_width=True):
        artifact = action(lambda: controller.call(
            "invoices", "issue", target_id, issued, due, description,
            st.session_state["invoice_issue_key"], group=group,
        ))
        if artifact:
            st.session_state["invoice_result"] = (selection, artifact.id)
            st.success("Fatura emitida e registrada no livro de emissões.")
    preview = st.session_state.get("invoice_preview")
    if preview and preview[0] == selection:
        st.download_button("Baixar prévia", preview[1], f"Previa_{label}.pdf", "application/pdf")
    result = st.session_state.get("invoice_result")
    if result and result[0] == selection:
        download(controller, result[1], "Baixar fatura emitida")


def _templates(controller, institutions, groups):
    scopes = {"default": (None, None, "Template padrão")}
    scopes.update({f"group:{item.id}": (item.id, None, f"Grupo: {item.nome}") for item in groups})
    scopes.update({f"link:{item.id}": (None, item.id, item.nome_instituicao) for item in institutions})
    selected = st.selectbox("Escopo do template", list(scopes), format_func=lambda key: scopes[key][2])
    group_id, link_id, _ = scopes[selected]
    current = controller.call("templates", "get_override", group_id=group_id, link_id=link_id)
    if link_id:
        resolved = controller.call("templates", "resolve", link_id)
    elif group_id:
        resolved = controller.call("templates", "resolve", group_id, group=True)
    else:
        resolved = controller.call("templates", "resolve_default")
    can_edit = controller.app.policy.allows(controller.identity, "billing.template.write")
    with st.form(f"template_{selected}_{current.revision if current else 0}"):
        st.caption("Desmarque um override para herdar o valor do nível anterior.")
        title_override = st.checkbox("Sobrescrever título", bool(current and current.title_text is not None))
        title = st.text_input("Título", current.title_text if current and current.title_text is not None else resolved.title_text)
        terms_override = st.checkbox("Sobrescrever termos de pagamento", bool(current and current.payment_terms is not None))
        terms = st.text_area("Termos de pagamento", current.payment_terms if current and current.payment_terms is not None else resolved.payment_terms)
        observation_mode = st.selectbox(
            "Observação", ["inherit", "show", "hide"],
            index=["inherit", "show", "hide"].index(current.observation_mode if current else "inherit"),
            format_func={"inherit": "Herdar", "show": "Exibir", "hide": "Ocultar"}.get,
        )
        observation = st.text_area("Texto da observação", current.observation_text if current and current.observation_text is not None else resolved.observation_text)
        a, b = st.columns(2)
        logos = ["gigafor-logo.png", "pop-ce-logo-preto.png", "rnp-logo-preto.png"]
        logo_override = a.checkbox("Sobrescrever logo", bool(current and current.logo_asset is not None))
        logo = a.selectbox("Logo", logos, index=logos.index(current.logo_asset if current and current.logo_asset else resolved.logo_asset))
        font_override = b.checkbox("Sobrescrever fonte", bool(current and current.font_family is not None))
        fonts = ["Arial", "Helvetica", "Times", "Courier"]
        font = b.selectbox("Fonte", fonts, index=fonts.index(current.font_family if current and current.font_family else resolved.font_family))
        color_override = st.checkbox("Sobrescrever cores", bool(current and current.primary_color is not None))
        c1, c2, c3 = st.columns(3)
        primary = c1.color_picker("Cor principal", current.primary_color if current and current.primary_color else resolved.primary_color)
        border = c2.color_picker("Bordas", current.border_color if current and current.border_color else resolved.border_color)
        text_color = c3.color_picker("Texto", current.text_color if current and current.text_color else resolved.text_color)
        size_override = st.checkbox("Sobrescrever tamanhos", bool(current and current.title_font_size is not None))
        s1, s2 = st.columns(2)
        title_size = s1.number_input("Tamanho do título", 16, 28, current.title_font_size if current and current.title_font_size else resolved.title_font_size)
        body_size = s2.number_input("Tamanho do corpo", 8, 12, current.body_font_size if current and current.body_font_size else resolved.body_font_size)
        period_mode = st.selectbox(
            "Exibir período", [None, True, False],
            index=[None, True, False].index(current.show_period if current else None),
            format_func=lambda value: {None: "Herdar", True: "Exibir", False: "Ocultar"}[value],
        )
        save = st.form_submit_button("Salvar template", type="primary", disabled=not can_edit)
    if save:
        value = InvoiceTemplateOverride(
            current.id if current else 0, group_id, link_id, "legacy_v1" if not current else current.base_version,
            title if title_override else None, terms if terms_override else None,
            observation_mode, observation if observation_mode == "show" else None,
            logo if logo_override else None, primary if color_override else None,
            border if color_override else None, text_color if color_override else None,
            font if font_override else None, int(title_size) if size_override else None,
            int(body_size) if size_override else None, period_mode,
            current.revision if current else 1,
        )
        if action(lambda: controller.call("templates", "save", value)) is not None:
            st.success("Template salvo.")
            st.rerun()
    if current and st.button("Descartar overrides", disabled=not can_edit, key=f"discard_{current.id}"):
        if action(lambda: controller.call(
            "templates", "discard", current.id, current.revision, group_id=group_id, link_id=link_id
        )) is not None:
            st.rerun()
    preview_target = None
    if link_id:
        preview_target = (link_id, False)
    elif group_id:
        preview_target = (group_id, True)
    elif institutions:
        preview_target = (institutions[0].id, False)
    if preview_target and st.button("Gerar prévia do template salvo", key=f"template_preview_{selected}"):
        target_id, group = preview_target
        content = action(lambda: controller.call(
            "invoices", "preview", target_id, date.today(), date.today() + timedelta(days=15),
            "Período de demonstração", group=group,
        ))
        if content:
            st.download_button(
                "Baixar prévia do template", content, "Previa_template.pdf", "application/pdf",
                key=f"template_preview_download_{selected}",
            )


def _sequences(controller, targets):
    if not targets:
        st.info("Nenhum alvo com perfil comercial.")
        return
    missing = []
    for schedule in controller.call("schedules", "list"):
        if not schedule.ativo or not schedule.incluir_fatura:
            continue
        scheduled = [(schedule.grupo_id, True)] if schedule.grupo_id else [
            (link_id, False) for link_id in schedule.link_ids
        ]
        for target_id, group in scheduled:
            if not controller.call("invoices", "sequence", target_id, group=group):
                missing.append(f"agendamento #{schedule.id}: {'grupo' if group else 'instituição'} {target_id}")
    if missing:
        st.warning("Agendamentos sem sequência: " + "; ".join(sorted(set(missing))))
    selected = st.selectbox("Alvo da sequência", list(targets), format_func=lambda key: targets[key][2], key="sequence_target")
    target_id, group, _ = targets[selected]
    current = controller.call("invoices", "sequence", target_id, group=group)
    can_edit = controller.app.policy.allows(controller.identity, "billing.sequence.write")
    with st.form(f"sequence_{selected}_{current.revision if current else 0}"):
        initial = st.number_input(
            "Número inicial", min_value=1, value=current.initial_value if current else 1,
            disabled=bool(current and current.next_value != current.initial_value),
        )
        prefix = st.text_input("Prefixo", current.prefix if current else "FAT")
        padding = st.number_input("Preenchimento com zeros", 0, 12, current.padding if current else 0)
        if current:
            st.metric("Próximo valor", current.next_value)
        save = st.form_submit_button("Salvar sequência", type="primary", disabled=not can_edit)
    if save and action(lambda: controller.call(
        "invoices", "save_sequence", target_id, initial, prefix, padding,
        group=group, revision=current.revision if current else 1,
    )) is not None:
        st.success("Sequência salva.")
        st.rerun()


def _ledger(controller):
    rows = controller.call("invoices", "ledger")
    if not rows:
        st.info("Nenhuma fatura emitida.")
        return
    display = [{
        "Número": row["display_number"],
        "Alvo": row["nome_instituicao"] or row["group_name"],
        "Emissão": row["issue_date"], "Vencimento": row["due_date"],
        "Origem": "Agendada" if row["execution_id"] else "Manual", "Status": row["status"],
    } for row in rows]
    data_table(display)
    labels = {row["id"]: f"{row['display_number']} — {row['nome_instituicao'] or row['group_name']}" for row in rows}
    selected = st.selectbox("Detalhes da emissão", list(labels), format_func=labels.get)
    row = next(item for item in rows if item["id"] == selected)
    download(controller, row["artifact_id"], "Baixar PDF", key=f"ledger_download_{selected}")
    if controller.app.policy.allows(controller.identity, "billing.ledger.void") and row["status"] == "issued":
        reason = st.text_area("Justificativa da anulação", key=f"void_reason_{selected}")
        if st.button("Anular emissão", key=f"void_{selected}"):
            if action(lambda: controller.call("invoices", "void", selected, reason)) is not None:
                st.rerun()
