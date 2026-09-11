from datetime import date, time
from html import escape

import streamlit as st
from sar.domain.models import Schedule
from sar.ui.components.common import heading, action


def _diagnostic_state(values):
    items = "".join(
        f"<div><dt>{escape(str(key).replace('_', ' '))}</dt>"
        f"<dd>{escape(str(value))}</dd></div>"
        for key, value in dict(values).items()
    )
    st.html(f'<section class="sar-diagnostic-state"><dl>{items}</dl></section>')


def _diagnostic_table(records, empty_message):
    rows = [dict(record) for record in records]
    if not rows:
        st.html(f'<div class="sar-diagnostic-empty">{escape(empty_message)}</div>')
        return
    columns = list(rows[0])
    header = "".join(f"<th>{escape(str(column).replace('_', ' '))}</th>" for column in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    st.html(
        '<div class="sar-diagnostic-table-wrap">'
        '<table class="sar-diagnostic-table">'
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody>"
        "</table></div>"
    )


def render(controller):
    heading("Automação de E-mail")
    state = controller.call("schedules", "state")
    if state["status"] == "synced":
        st.success("Agendamentos sincronizados com o crontab.")
    else:
        st.info("Agendamentos salvos no banco. Sincronização pendente pelo serviço Linux.")
    new, active, diagnostics = st.tabs(["Novo Agendamento", "Agendamentos Ativos", "Diagnóstico"])
    with new:
        schedule_form(controller)
    with active:
        schedules = controller.call("schedules", "list")
        if not schedules:
            st.info("Nenhum agendamento configurado ainda.")
        for schedule in schedules:
            with st.expander(f"#{schedule.id} | Dia {schedule.dia_envio} às {schedule.horario}"):
                st.write("Ativo" if schedule.ativo else "Pausado")
                st.write(
                    f"Grupo: {schedule.grupo_id}"
                    if schedule.grupo_id
                    else f"Instituições: {', '.join(map(str, schedule.link_ids))}"
                )
                st.write(
                    f"Fatura: {'Sim' if schedule.incluir_fatura else 'Não'}"
                )
                with st.container(horizontal=True, gap="small", wrap=False):
                    toggle_clicked = st.button(
                        "Pausar" if schedule.ativo else "Reativar",
                        key=f"pause_{schedule.id}",
                        icon=":material/pause:" if schedule.ativo else ":material/play_arrow:",
                        use_container_width=True,
                    )
                    delete_clicked = st.button(
                        "Excluir",
                        key=f"delete_{schedule.id}",
                        icon=":material/delete:",
                        use_container_width=True,
                    )
                if toggle_clicked:
                    if action(lambda: controller.call("schedules", "toggle", schedule.id)):
                        st.rerun()
                if delete_clicked:

                    def delete():
                        controller.call("schedules", "delete", schedule.id)
                        return True

                    if action(delete):
                        st.rerun()
                if st.toggle("Editar", key=f"edit_{schedule.id}"):
                    schedule_form(controller, schedule)
    with diagnostics:
        data = action(lambda: controller.call("schedules", "diagnostics"))
        if data:
            st.markdown("#### Estado do agendador")
            _diagnostic_state(data["scheduler"])
            if st.button("Ressincronizar Crontab Agora"):

                def request():
                    controller.call("schedules", "request_sync")
                    return True

                if action(request):
                    st.success("Ressincronização solicitada ao serviço Linux.")
            st.markdown("#### Execuções automáticas")
            _diagnostic_table(data["executions"], "Nenhuma execução registrada.")
            st.markdown("#### Auditoria operacional")
            _diagnostic_table(data["audit"], "Nenhum evento de auditoria registrado.")
            st.caption("O registro de auditoria é preservado; erros internos e credenciais não são exibidos.")


def schedule_form(controller, existing=None):
    key = str(existing.id) if existing else "new"
    links, groups = controller.call("schedules", "eligible")
    link_labels = {i.id: i.nome_instituicao for i in links}
    group_labels = {g.id: g.nome for g in groups}
    is_group = bool(existing.grupo_id) if existing else False
    mode = st.radio(
        "Modo de Agendamento:",
        ["Por Instituição", "Por Grupo"],
        index=int(is_group),
        disabled=bool(existing),
        horizontal=True,
        key=f"mode_{key}",
    )
    ids, group_id = [], None
    if mode == "Por Grupo":
        if not groups:
            st.warning("Nenhum grupo elegível: cadastre e-mail e vincule instituições.")
            return
        choices = list(group_labels)
        group_id = st.selectbox(
            "Grupos com E-mail e instituições vinculadas:",
            choices,
            format_func=group_labels.get,
            index=choices.index(existing.grupo_id) if existing and existing.grupo_id in choices else 0,
            disabled=bool(existing),
            key=f"group_{key}",
        )
    else:
        if not links:
            st.warning("Nenhuma instituição elegível: são necessários e-mail e perfil de fatura.")
            return
        ids = st.multiselect(
            "Apenas instituições com E-mail e Fatura cadastrados estão disponíveis:",
            list(link_labels),
            format_func=link_labels.get,
            default=[i for i in existing.link_ids if i in link_labels] if existing else [],
            key=f"ids_{key}",
        )
    a, b = st.columns(2)
    day = a.number_input(
        "Dia do mês para disparo:",
        min_value=1,
        max_value=28,
        value=existing.dia_envio if existing else 5,
        key=f"day_{key}",
    )
    when = b.time_input(
        "Horário de disparo:",
        value=time.fromisoformat(existing.horario) if existing else time(8),
        key=f"time_{key}",
    )
    mode = st.radio(
        "Selecione o período base para a extração:",
        ["Mês anterior completo (padrão)", "Período personalizado"],
        index=int(bool(existing and existing.periodo_modo == "personalizado")),
        key=f"period_{key}",
    )
    start = end = None
    if mode == "Período personalizado":
        a, b = st.columns(2)
        start = a.date_input(
            "Data início",
            date.fromisoformat(existing.data_inicio) if existing and existing.data_inicio else date.today(),
            key=f"start_{key}",
        ).isoformat()
        end = b.date_input(
            "Data fim",
            date.fromisoformat(existing.data_fim) if existing and existing.data_fim else date.today(),
            key=f"end_{key}",
        ).isoformat()
    include = st.toggle(
        "Incluir Fatura Comercial no envio",
        value=bool(existing.incluir_fatura) if existing else True,
        key=f"invoice_{key}",
    )
    prefix, due = "FAT", 15
    if include:
        st.caption("A numeração e o prefixo são definidos em Faturas → Sequências.")
        due = st.number_input(
            "Dia de vencimento da fatura:",
            min_value=1,
            max_value=28,
            value=existing.fatura_venc_dia if existing else 15,
            key=f"due_{key}",
        )
    if st.button(
        "Salvar Alterações" if existing else "Salvar Agendamento e Ativar", type="primary", key=f"save_{key}"
    ):
        value = Schedule(
            existing.id if existing else 0,
            tuple(ids),
            day,
            when.strftime("%H:%M"),
            include,
            prefix or "FAT",
            due,
            bool(existing.ativo) if existing else True,
            "personalizado" if start else "mes_anterior",
            start,
            end,
            group_id,
        )
        if action(lambda: controller.call("schedules", "save", value)):
            st.success("Salvo no banco; aguardando sincronização do serviço Linux.")
            st.rerun()
