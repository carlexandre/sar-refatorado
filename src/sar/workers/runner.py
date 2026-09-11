from datetime import datetime
from zoneinfo import ZoneInfo
from sar.application.dto import RunRequest
from sar.domain.errors import NotFound, ValidationError
from sar.workers.locking import exclusive_lock


def run_schedule(app, schedule_id, now=None):
    with exclusive_lock(app.settings.data_dir / "locks" / "worker.lock", wait=True):
        app.repo.recover_interrupted()
        schedule = app.repo.schedule(schedule_id)
        if not schedule:
            raise NotFound("Agendamento não encontrado.")
        if not schedule.ativo:
            raise ValidationError("Agendamento pausado.")
        now = now or datetime.now(ZoneInfo(app.settings.timezone))
        if now.day != schedule.dia_envio:
            raise ValidationError("Agendamento fora do dia de execução.")
        identity = app.identities.resolve(schedule.owner_id)
        app.schedules._authorize(identity, schedule)
        request = RunRequest(
            link_ids=schedule.link_ids, group_id=schedule.grupo_id,
            include_invoice=bool(schedule.incluir_fatura), invoice_due_day=schedule.fatura_venc_dia,
            start=schedule.data_inicio if schedule.periodo_modo == "personalizado" else None,
            end=schedule.data_fim if schedule.periodo_modo == "personalizado" else None,
            today=now.date(),
        )
        occurrence = f"schedule:{schedule.id}:{now:%Y-%m}:{schedule.dia_envio}:{schedule.horario}"
        return app.deliveries.run(identity, request, occurrence=occurrence, schedule_id=schedule.id)


def run_manual(app, request, identity=None):
    with exclusive_lock(app.settings.data_dir / "locks" / "worker.lock"):
        app.repo.recover_interrupted()
        return app.deliveries.run(identity or app.identities.current(), request)
