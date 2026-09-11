from html import escape
import re
import streamlit as st
from sar.security.redaction import public_error
from sar.domain.models import InvoiceItem


def action(callback):
    try:
        return callback()
    except Exception as error:
        st.error(public_error(error))
        return None


def navigate(page):
    pages = st.session_state.get("sar_navigation_pages", {})
    if page in pages:
        st.switch_page(pages[page])


def heading(title):
    left, right = st.columns([8, 2], vertical_alignment="center")
    left.html(
        '<div class="sar-page-intro">'
        '<div class="sar-eyebrow">Módulo</div>'
        f'<h1 class="sar-page-title">{escape(title)}</h1>'
        "</div>"
    )
    key = "back_home_" + re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")
    right.button(
        "Voltar ao início",
        key=key,
        icon=":material/arrow_back:",
        use_container_width=True,
        on_click=navigate,
        args=("Home",),
    )


def data_table(records, empty_message="Nenhum registro encontrado."):
    records = list(records)
    if not records:
        st.info(empty_message)
        return
    columns = list(records[0])
    header = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{escape(str(record.get(column, '') if record.get(column) is not None else ''))}</td>"
            for column in columns
        ) + "</tr>"
        for record in records
    )
    st.html(
        '<div class="sar-diagnostic-table-wrap">'
        f'<table class="sar-diagnostic-table"><thead><tr>{header}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def item_editor(values, key):
    state_key = f"{key}_rows"
    counter_key = f"{key}_next_row"
    if state_key not in st.session_state:
        initial = [
            {
                "row_id": index,
                "descricao": item.descricao,
                "quantidade": item.quantidade,
                "valor_unitario": item.valor_unitario,
            }
            for index, item in enumerate(values)
        ]
        st.session_state[state_key] = initial or [
            {"row_id": 0, "descricao": "", "quantidade": 1, "valor_unitario": 0.0}
        ]
        st.session_state[counter_key] = len(st.session_state[state_key])

    header = st.columns([4.7, 1.2, 1.8, 1.5], vertical_alignment="center")
    header[0].markdown("**Descrição**")
    header[1].markdown("**Qtd.**")
    header[2].markdown("**Valor unitário (R$)**")

    edited = []
    remove_id = None
    for row in st.session_state[state_key]:
        row_id = row["row_id"]
        columns = st.columns([4.7, 1.2, 1.8, 1.5], vertical_alignment="center")
        description = columns[0].text_input(
            "Descrição",
            value=row["descricao"],
            key=f"{key}_description_{row_id}",
            label_visibility="collapsed",
        )
        quantity = columns[1].number_input(
            "Quantidade",
            min_value=1,
            step=1,
            value=int(row["quantidade"]),
            key=f"{key}_quantity_{row_id}",
            label_visibility="collapsed",
        )
        unit_value = columns[2].number_input(
            "Valor unitário",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            value=float(row["valor_unitario"]),
            key=f"{key}_value_{row_id}",
            label_visibility="collapsed",
        )
        if columns[3].button(
            "Remover",
            icon=":material/delete:",
            key=f"{key}_remove_{row_id}",
            use_container_width=True,
        ):
            remove_id = row_id
        edited.append(
            {
                "row_id": row_id,
                "descricao": description,
                "quantidade": quantity,
                "valor_unitario": unit_value,
            }
        )

    st.session_state[state_key] = edited
    if remove_id is not None:
        st.session_state[state_key] = [row for row in edited if row["row_id"] != remove_id]
        st.rerun()

    if st.button("Adicionar item", icon=":material/add:", key=f"{key}_add"):
        row_id = st.session_state[counter_key]
        st.session_state[counter_key] = row_id + 1
        st.session_state[state_key].append(
            {"row_id": row_id, "descricao": "", "quantidade": 1, "valor_unitario": 0.0}
        )
        st.rerun()

    return [
        InvoiceItem(
            row.get("descricao") or "", int(row.get("quantidade") or 1), float(row.get("valor_unitario") or 0)
        )
        for row in edited
    ]


def commercial_fields(profile, key):
    left, right = st.columns(2)
    values = {}
    for field, label in (
        ("fatura_para", "Nome para a Fatura (Razão Social)"),
        ("cnpj", "CNPJ"),
        ("cep", "CEP"),
    ):
        values[field] = left.text_input(label, value=getattr(profile, field, ""), key=f"{key}_{field}")
    for field, label in (
        ("endereco", "Logradouro"),
        ("numero", "Número"),
        ("cidade", "Cidade"),
        ("uf", "UF"),
    ):
        values[field] = right.text_input(label, value=getattr(profile, field, ""), key=f"{key}_{field}")
    return values


def download(controller, artifact_id, label="Baixar PDF Agora", key=None):
    result = action(lambda: controller.call("history", "download", artifact_id))
    if result:
        artifact, content = result
        st.download_button(label, content, artifact.filename, "application/pdf", key=key)
