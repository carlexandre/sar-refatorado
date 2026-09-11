from sar.workers.locking import exclusive_lock
import sys
from pathlib import Path
from sar.domain.errors import ConfigurationError


def reconcile(app, scheduler):
    if sys.platform.startswith("linux"):
        expected = Path("/usr/share/zoneinfo") / app.settings.timezone
        local = Path("/etc/localtime")
        if not expected.is_file() or not local.is_file() or expected.read_bytes() != local.read_bytes():
            raise ConfigurationError(
                "Configure o fuso do servidor cron igual a SAR_TIMEZONE antes de sincronizar."
            )
    with exclusive_lock(app.settings.data_dir / "scheduler-locks" / "scheduler.lock"):
        state = app.repo.scheduler_state()
        scheduler.synchronize(app.repo.schedules())
        app.repo.scheduler_synced(state["desired_revision"])
        app.repo.audit("scheduler", "cron.synchronize", state["desired_revision"])
