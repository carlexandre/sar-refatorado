import os
from pathlib import Path
import re
import shlex
import subprocess
from sar.domain.errors import IntegrationError, ConfigurationError
from sar.security.validation import schedule as validate_schedule, identifier

MARKER = "# SAR-REFACTORED"
MANAGED = re.compile(r" # SAR-REFACTORED \[ID:\d+\]$")


class CronScheduler:
    def __init__(self, launcher: Path, run=subprocess.run):
        self.launcher = launcher
        self.run = run

    def read(self):
        try:
            result = self.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired):
            raise IntegrationError("Não foi possível ler o crontab; nenhuma alteração realizada.") from None
        if result.returncode == 0:
            return result.stdout
        if result.returncode == 1 and "no crontab for" in result.stderr.lower():
            return ""
        raise IntegrationError("Erro de leitura do crontab; sincronização cancelada.")

    def render(self, current, schedules):
        launcher = str(self.launcher)
        if not self.launcher.is_absolute() or any(c in launcher for c in ("\n", "\r", "%")):
            raise ConfigurationError("Caminho administrativo do launcher inválido para cron.")
        lines = [line for line in current.splitlines() if not MANAGED.search(line)]
        for schedule in schedules:
            if not schedule.ativo:
                continue
            validate_schedule(schedule)
            identifier(schedule.id)
            hour, minute = (int(part) for part in schedule.horario.split(":"))
            lines.append(
                f"{minute} {hour} {schedule.dia_envio} * * {shlex.quote(launcher)} {int(schedule.id)} {MARKER} [ID:{int(schedule.id)}]"
            )
        return "\n".join(lines).rstrip("\n") + "\n"

    def synchronize(self, schedules):
        current = self.read()
        content = self.render(current, schedules)
        if content == current:
            return
        # Protect against an external change observed before writing.
        if self.read() != current:
            raise IntegrationError("Crontab alterado durante sincronização; tente novamente.")
        try:
            result = self.run(["crontab", "-"], input=content, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            raise IntegrationError("Não foi possível atualizar o crontab.") from None
        if result.returncode:
            raise IntegrationError("O sistema recusou a atualização do crontab.")
