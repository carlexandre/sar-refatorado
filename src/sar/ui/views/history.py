from datetime import date, timedelta
import streamlit as st
from sar.ui.components.common import data_table, download, heading


def render(controller):
    heading("Histórico de Relatórios")
    all_rows = controller.call("history", "list")
    if not all_rows:
        st.info("Nenhum relatório foi gerado e salvo no banco de dados ainda.")
        return
    a, b, c = st.columns([2, 1, 1])
    search = a.text_input("Pesquisar por nome da Instituição:")
    group = b.selectbox("Filtrar por Grupo:", ["Todos"] + sorted({r["grupo"] for r in all_rows}))
    time_filter = c.selectbox(
        "Filtrar por Data:",
        ["Todo o tempo", "Hoje", "Últimos 7 dias", "Últimos 30 dias", "Últimos 3 meses", "Personalizado"],
    )
    start = end = None
    if time_filter == "Personalizado":
        a, b = st.columns(2)
        start = a.date_input("De:", date.today() - timedelta(days=7))
        end = b.date_input("Até:", date.today())
    rows = controller.call("history", "list", search, group, time_filter, start, end)
    data_table(
        [
            {
                "Data Geração": r["data_geracao"],
                "Grupo": r["grupo"],
                "Instituição": r["nome_instituicao"],
                "Período Referência": r["periodo_texto"],
            }
            for r in rows
        ],
    )
    st.markdown(f"#### Baixar Relatórios ({len(rows)} encontrados)")
    for row in rows[:15]:
        if row["artifact_id"]:
            download(
                controller,
                row["artifact_id"],
                f"{row['grupo']} | {row['nome_instituicao']} ({row['periodo_texto']}) - Gerado em: {row['data_geracao'][:16]}",
                key=f"history_{row['id']}",
            )
        else:
            st.error(f"Arquivo indisponível: {row['nome_instituicao']} ({row['periodo_texto']})")
