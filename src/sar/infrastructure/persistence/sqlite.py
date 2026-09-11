from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import re
from sar.domain.errors import ConfigurationError


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        if not self.path.is_file():
            raise ConfigurationError("Banco não inicializado. Execute sar migrate antes de iniciar.")
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        migration_root = Path(__file__).parents[2] / "migrations"
        migrations = []
        for script in sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql")):
            match = re.match(r"(\d+)_", script.name)
            if match:
                migrations.append((int(match.group(1)), script))
        expected = [version for version, _ in migrations]
        if not expected or expected != list(range(1, expected[-1] + 1)):
            raise ConfigurationError("Conjunto de migrações inválido.")
        if tables:
            if "schema_migrations" not in tables:
                raise ConfigurationError(
                    "Destino contém banco legado; use import-legacy em um destino vazio."
                )
            versions = [
                r[0] for r in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
            ]
            if versions != list(range(1, max(versions, default=0) + 1)) or not set(versions) <= set(expected):
                raise ConfigurationError("Versão de banco não suportada.")
        else:
            versions = []
        connection.execute("PRAGMA foreign_keys=ON")
        for version, script in migrations:
            if version in versions:
                continue
            sql = script.read_text(encoding="utf-8")
            connection.executescript("BEGIN IMMEDIATE;\n" + sql)
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                connection.rollback()
                raise ConfigurationError("Migração produziu referências inválidas.")
            connection.commit()
        connection.execute("PRAGMA journal_mode=WAL")
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    if os.name == "posix":
        # Dedicated service group only; permits the isolated cron reconciler to update state.
        path.chmod(0o660)
