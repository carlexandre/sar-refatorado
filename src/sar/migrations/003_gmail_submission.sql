ALTER TABLE outbox ADD COLUMN smtp_accepted_at TEXT;
INSERT INTO schema_migrations(version) VALUES (3);
