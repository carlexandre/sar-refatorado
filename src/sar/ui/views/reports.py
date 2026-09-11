from datetime import date, timedelta
import streamlit as st
from sar.domain.periods import validate_period
from sar.ui.components.common import heading, action, download


def render(controller):
    heading("Gerar Novo Relatório")
    options = controller.call("registrations", "report_options")
    if not options:
        st.info("Nenhuma Instituição cadastrada ainda. Vá para 'Gerenciar Instituições'.")
        return
    left, right = st.columns([2, 1])
    search = left.text_input("Pesquisar por nome da Instituição:")
    group = right.selectbox("Filtrar por Grupo:", ["Todos"] + sorted({g for _, g in options}))
    options = [
        (i, g)
        for i, g in options
        if search.casefold() in i.nome_instituicao.casefold() and (group == "Todos" or g == group)
    ]
    labels = {i.id: f"{g} - {i.nome_instituicao}" for i, g in options}
    left, right = st.columns([2, 1])
    ids = left.multiselect(
        "Selecione até 3 Instituições:", list(labels), format_func=labels.get, max_selections=3
    )
    start = right.date_input("Data Início", value=date.today() - timedelta(days=30))
    end = right.date_input("Data Fim", value=date.today())
    if st.button("Gerar Relatório e Salvar", type="primary", disabled=not ids):
        with st.spinner("Consultando Zabbix, processando gráficos e montando o PDF..."):
            result = action(lambda: controller.call("reports", "generate", ids, validate_period(start, end)))
        if result:
            st.session_state["report_result"] = (tuple(ids), start, end, result.artifact.id)
            st.success("Relatório salvo no histórico com sucesso!")
    saved = st.session_state.get("report_result")
    if saved and saved[:3] == (tuple(ids), start, end):
        download(controller, saved[3])
