import hashlib
import sqlite3
import pytest
from sar.infrastructure.persistence.migration import import_legacy
from sar.infrastructure.persistence.sqlite import Database
from sar.domain.errors import ValidationError


def test_old_schema_orphans_and_missing_file(tmp_path):
    old = tmp_path / "legacy"
    old.mkdir()
    (old / "pdfs_gerados").mkdir()
    (old / "pdfs_gerados" / "known.pdf").write_bytes(b"%PDF-1.7 known")
    source = old / "old.db"
    with sqlite3.connect(source) as c:
        c.executescript("""
        CREATE TABLE grupos(id INTEGER PRIMARY KEY,nome TEXT);
        CREATE TABLE links(id INTEGER PRIMARY KEY,grupo_id INTEGER,nome_instituicao TEXT,host_id TEXT,item_down_id TEXT,item_up_id TEXT,capacidade_str TEXT);
        CREATE TABLE faturas_cadastradas(id INTEGER PRIMARY KEY,link_id INTEGER,fatura_para TEXT);
        CREATE TABLE historico_relatorios(id INTEGER PRIMARY KEY,link_id INTEGER,data_geracao TEXT,periodo_texto TEXT,caminho_arquivo TEXT);
        INSERT INTO grupos VALUES (1,'Grupo');
        INSERT INTO links VALUES (1,1,'Instituição','10','11','12','1 Gbps');
        INSERT INTO faturas_cadastradas VALUES (1,1,'Cliente');
        INSERT INTO faturas_cadastradas VALUES (2,999,'Orphan');
        INSERT INTO historico_relatorios VALUES (1,1,'2024-01-01','mês','pdfs_gerados/known.pdf');
        INSERT INTO historico_relatorios VALUES (2,999,'2024-01-01','mês','pdfs_gerados/known.pdf');
        INSERT INTO historico_relatorios VALUES (3,1,'2024-01-01','mês','../../private.pdf');
        """)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "new" / "sar.db"
    result = import_legacy(source, destination, old / "pdfs_gerados", tmp_path / "new" / "artifacts")
    assert result["tables"]["faturas_cadastradas"] == {"source": 2, "imported": 1, "reconciliation": 1}
    assert result["tables"]["historico_relatorios"] == {"source": 3, "imported": 2, "reconciliation": 1}
    assert result["copied_artifacts"] == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    with Database(destination).connect() as c:
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        assert c.execute("SELECT COUNT(*) FROM historico_relatorios WHERE missing_file=1").fetchone()[0] == 1
        assert (
            c.execute("SELECT COUNT(*) FROM reconciliation WHERE reason='unknown_legacy_scope'").fetchone()[0]
            == 1
        )
    with pytest.raises(ValidationError):
        import_legacy(source, destination, old / "pdfs_gerados", tmp_path / "new" / "artifacts")
