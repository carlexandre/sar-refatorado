CREATE TABLE app_users (
 id TEXT PRIMARY KEY,
 username TEXT NOT NULL COLLATE NOCASE UNIQUE,
 display_name TEXT NOT NULL,
 email TEXT,
 auth_provider TEXT NOT NULL DEFAULT 'local' CHECK(auth_provider IN ('local','ldap')),
 external_subject TEXT,
 password_hash TEXT,
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 must_change_password INTEGER NOT NULL DEFAULT 1 CHECK(must_change_password IN (0,1)),
 global_scope INTEGER NOT NULL DEFAULT 0 CHECK(global_scope IN (0,1)),
 failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts >= 0),
 locked_until TEXT, last_login_at TEXT, password_changed_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((auth_provider='local' AND password_hash IS NOT NULL) OR
       (auth_provider='ldap' AND password_hash IS NULL))
);
CREATE UNIQUE INDEX app_users_external_subject_idx
 ON app_users(auth_provider, external_subject) WHERE external_subject IS NOT NULL;

CREATE TABLE roles (code TEXT PRIMARY KEY, description TEXT NOT NULL);
INSERT INTO roles(code,description) VALUES
 ('consultation','Consulta de relatórios'),
 ('operations','Operação e cadastros'),
 ('billing','Faturamento e entregas'),
 ('administration','Administração global');
CREATE TABLE user_roles (
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 role_code TEXT NOT NULL REFERENCES roles(code), PRIMARY KEY(user_id,role_code)
);
CREATE TABLE user_group_scopes (
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 group_id INTEGER NOT NULL REFERENCES grupos(id), PRIMARY KEY(user_id,group_id)
);
CREATE TABLE user_institution_scopes (
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 link_id INTEGER NOT NULL REFERENCES links(id), PRIMARY KEY(user_id,link_id)
);
CREATE TABLE auth_sessions (
 token_hash TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 idle_expires_at TEXT NOT NULL, absolute_expires_at TEXT NOT NULL,
 revoked_at TEXT
);
CREATE INDEX auth_sessions_user_idx ON auth_sessions(user_id);

CREATE TABLE invoice_template_overrides (
 id INTEGER PRIMARY KEY,
 group_id INTEGER REFERENCES grupos(id), link_id INTEGER REFERENCES links(id),
 base_version TEXT, title_text TEXT, payment_terms TEXT,
 observation_mode TEXT NOT NULL DEFAULT 'inherit' CHECK(observation_mode IN ('inherit','show','hide')),
 observation_text TEXT, logo_asset TEXT,
 primary_color TEXT, border_color TEXT, text_color TEXT, font_family TEXT,
 title_font_size INTEGER CHECK(title_font_size BETWEEN 16 AND 28),
 body_font_size INTEGER CHECK(body_font_size BETWEEN 8 AND 12),
 show_period INTEGER CHECK(show_period IS NULL OR show_period IN (0,1)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 updated_by TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(group_id IS NULL OR link_id IS NULL)
);
CREATE UNIQUE INDEX invoice_template_default_idx ON invoice_template_overrides((1))
 WHERE group_id IS NULL AND link_id IS NULL;
CREATE UNIQUE INDEX invoice_template_group_idx ON invoice_template_overrides(group_id)
 WHERE group_id IS NOT NULL;
CREATE UNIQUE INDEX invoice_template_link_idx ON invoice_template_overrides(link_id)
 WHERE link_id IS NOT NULL;

CREATE TABLE invoice_sequences (
 id INTEGER PRIMARY KEY,
 group_id INTEGER REFERENCES grupos(id), link_id INTEGER REFERENCES links(id),
 initial_value INTEGER NOT NULL CHECK(initial_value > 0),
 next_value INTEGER NOT NULL CHECK(next_value >= initial_value),
 prefix TEXT NOT NULL DEFAULT 'FAT',
 padding INTEGER NOT NULL DEFAULT 0 CHECK(padding BETWEEN 0 AND 12),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 updated_by TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((group_id IS NOT NULL AND link_id IS NULL) OR
       (group_id IS NULL AND link_id IS NOT NULL))
);
CREATE UNIQUE INDEX invoice_sequence_group_idx ON invoice_sequences(group_id)
 WHERE group_id IS NOT NULL;
CREATE UNIQUE INDEX invoice_sequence_link_idx ON invoice_sequences(link_id)
 WHERE link_id IS NOT NULL;

CREATE TABLE invoice_issuances (
 id TEXT PRIMARY KEY,
 sequence_id INTEGER NOT NULL REFERENCES invoice_sequences(id),
 sequence_value INTEGER NOT NULL CHECK(sequence_value > 0),
 display_number TEXT NOT NULL,
 artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id),
 execution_id TEXT REFERENCES executions(id),
 idempotency_key TEXT NOT NULL UNIQUE,
 issue_date TEXT NOT NULL, due_date TEXT NOT NULL, period_text TEXT NOT NULL,
 template_version TEXT NOT NULL, template_snapshot_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'issued' CHECK(status IN ('issued','void')),
 created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 voided_by TEXT, voided_at TEXT, void_reason TEXT,
 UNIQUE(sequence_id,sequence_value), UNIQUE(sequence_id,display_number)
);
CREATE INDEX invoice_issuances_created_idx ON invoice_issuances(created_at DESC);

INSERT INTO reconciliation(source_table,source_id,reason,payload)
 SELECT 'artifacts',id,'invoice_sequence_not_reconstructed','{}'
 FROM artifacts WHERE kind='invoice';
INSERT INTO schema_migrations(version) VALUES (2);
