"""Read-only legacy import. Destination must be a newly initialized, empty database."""

from dataclasses import fields, MISSING
import json
from pathlib import Path
import sqlite3
from sar.domain.errors import ValidationError
from sar.domain.models import Group, Institution, CommercialProfile, Schedule
from sar.security.validation import schedule as validate_schedule
from sar.infrastructure.persistence.sqlite import initialize, Database
from sar.infrastructure.storage.local_artifacts import LocalArtifacts
from sar.infrastructure.persistence.migration_sql import SELECTS, INSERTS


def import_legacy(source: Path, destination: Path, source_artifacts: Path, target_artifacts: Path):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination or target_artifacts.resolve() == source_artifacts.resolve():
        raise ValidationError("Origem e destino da migração devem ser diferentes.")
    if destination.exists():
        raise ValidationError("A importação exige um banco de destino inexistente.")
    initialize(destination)
    store = LocalArtifacts(target_artifacts)
    legacy = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    counts = {}
    copied = []
    try:
        legacy.execute("BEGIN")
        tables = {r[0] for r in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with Database(destination).connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            def rows(table):
                # table names below are fixed application constants, never user input.
                values = [dict(r) for r in legacy.execute(SELECTS[table])] if table in tables else []
                counts[table] = {"source": len(values), "imported": 0, "reconciliation": 0}
                return values

            def quarantine(table, row, reason):
                conn.execute(
                    "INSERT INTO reconciliation(source_table,source_id,reason,payload) VALUES (?,?,?,?)",
                    (
                        table,
                        str(row.get("id", row.get("link_id", ""))),
                        reason,
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
                counts[table]["reconciliation"] += 1

            def insert(table, row, cls=None):
                data = {}
                if cls:
                    for field in fields(cls):
                        default = field.default if field.default is not MISSING else None
                        data[field.name] = row.get(field.name, default)
                        if data[field.name] is None and isinstance(default, str):
                            data[field.name] = default
                else:
                    data = row
                query = INSERTS[table]
                columns = query.split("(", 1)[1].split(")", 1)[0].split(",")
                conn.execute(query, tuple(data.get(column) for column in columns))
                counts[table]["imported"] += 1

            pending = rows("grupos")
            known = set()
            while pending:
                ready = [r for r in pending if not r.get("parent_id") or r["parent_id"] in known]
                if not ready:
                    for row in pending:
                        quarantine("grupos", row, "invalid_or_cyclic_parent")
                    break
                for row in ready:
                    try:
                        insert("grupos", row, Group)
                        known.add(row["id"])
                    except sqlite3.IntegrityError:
                        quarantine("grupos", row, "invalid_group")
                    pending.remove(row)

            valid_links = set()
            for row in rows("links"):
                try:
                    insert("links", row, Institution)
                    valid_links.add(row["id"])
                except sqlite3.IntegrityError:
                    quarantine("links", row, "missing_group")
            for row in rows("faturas_cadastradas"):
                try:
                    insert("faturas_cadastradas", row, CommercialProfile)
                except sqlite3.IntegrityError:
                    quarantine("faturas_cadastradas", row, "missing_institution_or_duplicate")
            for table in ("itens_fatura", "itens_fatura_grupo"):
                for row in rows(table):
                    try:
                        insert(table, row)
                    except sqlite3.IntegrityError:
                        quarantine(table, row, "invalid_item_or_missing_parent")

            for row in rows("agendamentos"):
                try:
                    ids = json.loads(row.get("link_ids", "[]"))
                    data = {
                        f.name: row.get(f.name, f.default if f.default is not MISSING else None)
                        for f in fields(Schedule)
                    }
                    data["link_ids"] = tuple(ids)
                    candidate = Schedule(**data)
                    validate_schedule(candidate)
                    if not set(ids) <= valid_links or (
                        candidate.grupo_id and candidate.grupo_id not in known
                    ):
                        raise ValueError
                    data["link_ids"] = json.dumps(ids)
                    insert("agendamentos", data)
                except (ValueError, TypeError, ValidationError, sqlite3.IntegrityError):
                    quarantine("agendamentos", row, "invalid_schedule")

            cache = {}
            root = source_artifacts.resolve(strict=True)
            history = rows("historico_relatorios")
            for row in history:
                if row["link_id"] not in valid_links:
                    quarantine("historico_relatorios", row, "missing_institution")
                    continue
                original = Path(row["caminho_arquivo"])
                candidate = original if original.is_absolute() else source.parent / original
                # Legacy paths belong to the explicitly selected legacy artifacts directory only.
                resolved = candidate.resolve()
                safe = resolved.is_relative_to(root) and not candidate.is_symlink()
                artifact = None
                if safe and resolved.is_file():
                    if resolved not in cache:
                        artifact = store.save(resolved.read_bytes(), resolved.name)
                        copied.append(artifact.id)
                        cache[resolved] = artifact
                        conn.execute(
                            "INSERT INTO artifacts(id,filename,sha256,size,template_version) VALUES (?,?,?,?,?)",
                            (
                                artifact.id,
                                artifact.filename,
                                artifact.sha256,
                                artifact.size,
                                artifact.template_version,
                            ),
                        )
                    artifact = cache[resolved]
                    conn.execute(
                        "INSERT OR IGNORE INTO artifact_institutions VALUES (?,?)",
                        (artifact.id, row["link_id"]),
                    )
                conn.execute(
                    "INSERT INTO historico_relatorios(id,link_id,data_geracao,periodo_texto,artifact_id,missing_file) VALUES (?,?,?,?,?,?)",
                    (
                        row["id"],
                        row["link_id"],
                        row["data_geracao"],
                        row["periodo_texto"],
                        artifact.id if artifact else None,
                        int(artifact is None),
                    ),
                )
                counts["historico_relatorios"]["imported"] += 1
                if artifact is None:
                    conn.execute(
                        "INSERT INTO reconciliation(source_table,source_id,reason,payload) VALUES (?,?,?,?)",
                        ("artifact_reference", str(row["id"]), "unsafe_or_missing_file", json.dumps(row)),
                    )
            # Preserve every PDF in the authorized root, including files absent from valid history.
            inventory = list(root.rglob("*.pdf"))
            for original in inventory:
                resolved = original.resolve()
                if original.is_symlink() or not resolved.is_relative_to(root):
                    raise ValidationError("Inventário contém link de arquivo não permitido.")
                if resolved not in cache:
                    artifact = store.save(resolved.read_bytes(), resolved.name)
                    copied.append(artifact.id)
                    cache[resolved] = artifact
                    conn.execute(
                        "INSERT INTO artifacts(id,filename,sha256,size,template_version) VALUES (?,?,?,?,?)",
                        (
                            artifact.id,
                            artifact.filename,
                            artifact.sha256,
                            artifact.size,
                            artifact.template_version,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO reconciliation(source_table,source_id,reason,payload) VALUES (?,?,?,?)",
                        (
                            "artifact_scope",
                            artifact.id,
                            "no_valid_history",
                            json.dumps({"legacy_name": str(original.relative_to(root))}),
                        ),
                    )
            # A consolidated legacy artifact may include an orphan institution; never expose it by partial scope.
            for row in history:
                if row["link_id"] not in valid_links:
                    original = Path(row["caminho_arquivo"])
                    resolved = (original if original.is_absolute() else source.parent / original).resolve()
                    if resolved in cache:
                        artifact = cache[resolved]
                        conn.execute(
                            "INSERT INTO reconciliation(source_table,source_id,reason,payload) VALUES (?,?,?,?)",
                            ("artifact_scope", artifact.id, "unknown_legacy_scope", "{}"),
                        )
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise ValidationError("A migração deixou referências inválidas.")
            for table, count in counts.items():
                if count["source"] != count["imported"] + count["reconciliation"]:
                    raise ValidationError("Contagem de migração inconsistente.")
    except BaseException:
        for identifier in copied:
            store.remove_unregistered(identifier)
        raise
    finally:
        legacy.close()
    return {"tables": counts, "copied_artifacts": len(copied), "foreign_key_issues": 0}
