from pathlib import Path
import os
import stat
from sar.domain.errors import ConfigurationError


class RuntimeCredentials:
    def __init__(self, directory: Path | None):
        self.directory = directory

    def get(self, name: str) -> str | None:
        if name not in {"zabbix-token", "zabbix-user", "zabbix-password"}:
            raise ConfigurationError("Credencial desconhecida.")
        if not self.directory:
            return None
        root = self.directory.resolve(strict=True)
        path = self.directory / name
        if not path.exists():
            return None
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ConfigurationError("Caminho de credencial inválido.")
        if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ConfigurationError("Credencial acessível por outros usuários.")
        value = path.read_text(encoding="utf-8").strip()
        if not value or len(value) > 16384:
            raise ConfigurationError("Conteúdo de credencial inválido.")
        return value
