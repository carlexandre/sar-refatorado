from dataclasses import replace
from sar.domain.errors import ValidationError, NotFound
from sar.security.validation import schedule as validate_schedule


class Schedules:
    def __init__(self, repo, policy):
        self.repo, self.policy = repo, policy

    def _authorize(self, identity, schedule, action="schedules.write"):
        self.policy.require(
            identity,
            action,
            self.repo.group_links(schedule.grupo_id) if schedule.grupo_id else schedule.link_ids,
            [schedule.grupo_id] if schedule.grupo_id else [],
        )

    def list(self, identity):
        self.policy.require(identity, "schedules.read")
        from sar.domain.errors import AccessDenied

        result = []
        for schedule in self.repo.schedules():
            try:
                self._authorize(identity, schedule, "schedules.read")
                result.append(schedule)
            except AccessDenied:
                continue
        return result

    def eligible(self, identity):
        self.policy.require(identity, "schedules.read")
        links = [
            i
            for i in self.repo.institutions()
            if i.email_contato.strip()
            and self.repo.profile(i.id)
            and (identity.global_scope or i.id in identity.institution_ids)
        ]
        groups = [
            g
            for g in self.repo.groups()
            if g.email_contato.strip()
            and self.repo.group_links(g.id)
            and (
                identity.global_scope
                or (
                    g.id in identity.group_ids
                    and set(self.repo.group_links(g.id)) <= identity.institution_ids
                )
            )
        ]
        return links, groups

    def save(self, identity, schedule):
        validate_schedule(schedule)
        self._authorize(identity, schedule)
        if schedule.id:
            previous = self.repo.schedule(schedule.id)
            if not previous:
                raise NotFound("Agendamento não encontrado.")
            self._authorize(identity, previous)
            schedule = replace(schedule, owner_id=previous.owner_id)
        else:
            schedule = replace(schedule, owner_id=identity.subject)
        links, groups = self.eligible(identity)
        if schedule.grupo_id:
            if schedule.grupo_id not in {g.id for g in groups}:
                raise ValidationError("Grupo sem contato ou instituições elegíveis.")
        elif not set(schedule.link_ids) <= {i.id for i in links}:
            raise ValidationError("Instituições precisam de e-mail e perfil de fatura.")
        if schedule.incluir_fatura:
            targets = [(schedule.grupo_id, True)] if schedule.grupo_id else [
                (link_id, False) for link_id in schedule.link_ids
            ]
            missing = [target_id for target_id, group in targets if not self.repo.invoice_sequence(target_id, group)]
            if missing:
                raise ValidationError(
                    "Configure a sequência de fatura para todos os alvos antes de ativar o agendamento."
                )
        saved = self.repo.save_schedule(schedule)
        self.repo.audit(identity.subject, "schedules.save", saved)
        return saved

    def toggle(self, identity, schedule_id):
        schedule = self.repo.schedule(schedule_id)
        if not schedule:
            raise NotFound("Agendamento não encontrado.")
        self._authorize(identity, schedule)
        if schedule.ativo:
            saved = self.repo.save_schedule(replace(schedule, ativo=False))
            self.repo.audit(identity.subject, "schedules.pause", saved)
            return saved
        return self.save(identity, replace(schedule, ativo=not schedule.ativo))

    def delete(self, identity, schedule_id):
        schedule = self.repo.schedule(schedule_id)
        if not schedule:
            raise NotFound("Agendamento não encontrado.")
        self._authorize(identity, schedule)
        self.repo.delete_schedule(schedule_id)
        self.repo.audit(identity.subject, "schedules.delete", schedule_id)

    def state(self, identity):
        self.policy.require(identity, "schedules.read")
        return self.repo.scheduler_state()

    def request_sync(self, identity):
        self.policy.require(identity, "admin.diagnostics")
        self.repo.request_sync()

    def diagnostics(self, identity):
        self.policy.require(identity, "admin.diagnostics")
        return {
            "scheduler": self.repo.scheduler_state(),
            "executions": self.repo.executions(),
            "audit": self.repo.audit_recent(),
        }
