CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE grupos (
 id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, parent_id INTEGER REFERENCES grupos(id),
 email_contato TEXT NOT NULL DEFAULT '', fatura_para TEXT NOT NULL DEFAULT '', cnpj TEXT NOT NULL DEFAULT '',
 cep TEXT NOT NULL DEFAULT '', endereco TEXT NOT NULL DEFAULT '', numero TEXT NOT NULL DEFAULT '',
 cidade TEXT NOT NULL DEFAULT '', uf TEXT NOT NULL DEFAULT ''
);
CREATE TABLE links (
 id INTEGER PRIMARY KEY, grupo_id INTEGER NOT NULL REFERENCES grupos(id), nome_instituicao TEXT NOT NULL,
 host_id TEXT NOT NULL, item_down_id TEXT NOT NULL, item_up_id TEXT NOT NULL, capacidade_str TEXT NOT NULL,
 email_contato TEXT NOT NULL DEFAULT ''
);
CREATE TABLE faturas_cadastradas (
 link_id INTEGER PRIMARY KEY REFERENCES links(id), fatura_para TEXT NOT NULL, cnpj TEXT NOT NULL DEFAULT '',
 cep TEXT NOT NULL DEFAULT '', endereco TEXT NOT NULL DEFAULT '', numero TEXT NOT NULL DEFAULT '',
 cidade TEXT NOT NULL DEFAULT '', uf TEXT NOT NULL DEFAULT '', email_contato TEXT NOT NULL DEFAULT ''
);
CREATE TABLE itens_fatura (
 id INTEGER PRIMARY KEY, link_id INTEGER NOT NULL REFERENCES links(id), descricao TEXT NOT NULL,
 quantidade INTEGER NOT NULL CHECK(quantidade > 0), valor_unitario REAL NOT NULL
);
CREATE TABLE itens_fatura_grupo (
 id INTEGER PRIMARY KEY, grupo_id INTEGER NOT NULL REFERENCES grupos(id), descricao TEXT NOT NULL,
 quantidade INTEGER NOT NULL CHECK(quantidade > 0), valor_unitario REAL NOT NULL
);
CREATE TABLE artifacts (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
 template_version TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'report' CHECK(kind IN ('report','invoice')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE artifact_institutions (
 artifact_id TEXT NOT NULL REFERENCES artifacts(id), link_id INTEGER NOT NULL REFERENCES links(id),
 PRIMARY KEY(artifact_id, link_id)
);
CREATE TABLE historico_relatorios (
 id INTEGER PRIMARY KEY, link_id INTEGER NOT NULL REFERENCES links(id),
 data_geracao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, periodo_texto TEXT NOT NULL,
 artifact_id TEXT REFERENCES artifacts(id), missing_file INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE agendamentos (
 id INTEGER PRIMARY KEY, link_ids TEXT NOT NULL, dia_envio INTEGER NOT NULL CHECK(dia_envio BETWEEN 1 AND 28),
 horario TEXT NOT NULL, incluir_fatura INTEGER NOT NULL DEFAULT 1, fatura_num_prefixo TEXT NOT NULL DEFAULT 'FAT',
 fatura_venc_dia INTEGER NOT NULL DEFAULT 15 CHECK(fatura_venc_dia BETWEEN 1 AND 28), ativo INTEGER NOT NULL DEFAULT 1,
 periodo_modo TEXT NOT NULL DEFAULT 'mes_anterior', data_inicio TEXT, data_fim TEXT,
 grupo_id INTEGER REFERENCES grupos(id), owner_id TEXT NOT NULL DEFAULT 'internal-team'
);
CREATE TABLE scheduler_state (
 id INTEGER PRIMARY KEY CHECK(id=1), desired_revision INTEGER NOT NULL DEFAULT 0,
 synced_revision INTEGER NOT NULL DEFAULT -1, status TEXT NOT NULL DEFAULT 'pending'
);
INSERT INTO scheduler_state(id) VALUES (1);
CREATE TABLE executions (
 id TEXT PRIMARY KEY, occurrence TEXT UNIQUE NOT NULL, schedule_id INTEGER,
 owner_id TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT, result_json TEXT
);
CREATE TABLE outbox (
 id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id),
 payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE reconciliation (
 id INTEGER PRIMARY KEY, source_table TEXT NOT NULL, source_id TEXT, reason TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE audit_events (
 id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 subject TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL, outcome TEXT NOT NULL
);
CREATE INDEX history_link_idx ON historico_relatorios(link_id);
CREATE INDEX outbox_status_idx ON outbox(status);
INSERT INTO schema_migrations(version) VALUES (1);
