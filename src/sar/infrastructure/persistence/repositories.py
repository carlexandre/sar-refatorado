from dataclasses import asdict, fields
import json
import sqlite3
from sar.domain.models import (
    Group, Institution, CommercialProfile, InvoiceItem, Schedule, Artifact,
    AppUser, InvoiceTemplateOverride, InvoiceSequence,
)
from sar.domain.errors import NotFound, ValidationError, ConcurrencyError
from sar.infrastructure.persistence.unit_of_work import UnitOfWork


def model(cls, row):
    if row is None:
        raise NotFound("Registro não encontrado.")
    return cls(**{field.name: row[field.name] for field in fields(cls)})


class Repository:
    """SQL boundary. Compound business mutations are atomic here."""

    def __init__(self, database):
        self.database = database

    def _all(self, sql, params=()):
        with self.database.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def groups(self):
        return [model(Group, r) for r in self._all("SELECT * FROM grupos ORDER BY nome")]

    def group(self, group_id):
        rows = self._all("SELECT * FROM grupos WHERE id=?", (group_id,))
        return model(Group, rows[0] if rows else None)

    def institutions(self):
        return [model(Institution, r) for r in self._all("SELECT * FROM links ORDER BY nome_instituicao")]

    def institution(self, link_id):
        rows = self._all("SELECT * FROM links WHERE id=?", (link_id,))
        return model(Institution, rows[0] if rows else None)

    def profile(self, link_id):
        rows = self._all("SELECT * FROM faturas_cadastradas WHERE link_id=?", (link_id,))
        return model(CommercialProfile, rows[0]) if rows else None

    def invoice_items(self, target_id, group=False):
        table, key = ("itens_fatura_grupo", "grupo_id") if group else ("itens_fatura", "link_id")
        return [
            model(InvoiceItem, r)
            for r in self._all(
                (
                    "SELECT descricao, quantidade, valor_unitario FROM itens_fatura_grupo WHERE grupo_id=? ORDER BY id"
                    if group
                    else "SELECT descricao, quantidade, valor_unitario FROM itens_fatura WHERE link_id=? ORDER BY id"
                ),
                (target_id,),
            )
        ]

    def group_links(self, group_id):
        # UNION, not UNION ALL, terminates even if an imported hierarchy contains a cycle.
        return [
            r["id"]
            for r in self._all(
                """WITH RECURSIVE descendants(id) AS (
            SELECT id FROM grupos WHERE id=? UNION
            SELECT g.id FROM grupos g JOIN descendants d ON g.parent_id=d.id)
            SELECT id FROM links WHERE grupo_id IN (SELECT id FROM descendants) ORDER BY id""",
                (group_id,),
            )
        ]

    def group_ancestors(self, group_id):
        rows = self._all(
            """WITH RECURSIVE ancestors(id,parent_id,depth) AS (
            SELECT id,parent_id,0 FROM grupos WHERE id=? UNION
            SELECT g.id,g.parent_id,a.depth+1 FROM grupos g JOIN ancestors a ON a.parent_id=g.id)
            SELECT id FROM ancestors ORDER BY depth DESC""",
            (group_id,),
        )
        return [row["id"] for row in rows]

    # Authentication and identity directory.
    def user(self, user_id):
        rows = self._all("SELECT * FROM app_users WHERE id=?", (user_id,))
        return model(AppUser, rows[0] if rows else None)

    def user_by_username(self, username):
        rows = self._all("SELECT * FROM app_users WHERE username=? COLLATE NOCASE", (username,))
        return model(AppUser, rows[0]) if rows else None

    def users(self):
        return [model(AppUser, row) for row in self._all("SELECT * FROM app_users ORDER BY username")]

    def user_roles(self, user_id):
        return frozenset(row["role_code"] for row in self._all(
            "SELECT role_code FROM user_roles WHERE user_id=?", (user_id,)
        ))

    def user_scopes(self, user_id):
        groups = {row["group_id"] for row in self._all(
            "SELECT group_id FROM user_group_scopes WHERE user_id=?", (user_id,)
        )}
        explicit = {row["link_id"] for row in self._all(
            "SELECT link_id FROM user_institution_scopes WHERE user_id=?", (user_id,)
        )}
        effective = set(explicit)
        for group_id in groups:
            effective.update(self.group_links(group_id))
        return frozenset(groups), frozenset(effective)

    def create_user(self, user: AppUser, roles, group_ids=(), link_ids=()):
        data = asdict(user)
        for key in ("last_login_at", "password_changed_at"):
            data.pop(key)
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            try:
                conn.execute(
                    """INSERT INTO app_users
                    (id,username,display_name,email,auth_provider,external_subject,password_hash,
                     is_active,must_change_password,global_scope,failed_attempts,locked_until)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    tuple(data.values()),
                )
                self._replace_access(conn, user.id, roles, group_ids, link_ids)
            except sqlite3.IntegrityError:
                raise ValidationError("Usuário duplicado, perfil ou escopo inválido.") from None

    @staticmethod
    def _replace_access(conn, user_id, roles, group_ids, link_ids):
        conn.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM user_group_scopes WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM user_institution_scopes WHERE user_id=?", (user_id,))
        conn.executemany("INSERT INTO user_roles VALUES (?,?)", [(user_id, role) for role in set(roles)])
        conn.executemany(
            "INSERT INTO user_group_scopes VALUES (?,?)", [(user_id, value) for value in set(group_ids)]
        )
        conn.executemany(
            "INSERT INTO user_institution_scopes VALUES (?,?)", [(user_id, value) for value in set(link_ids)]
        )

    def update_user_access(self, user_id, *, display_name, email, active, global_scope, roles, group_ids, link_ids):
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            if conn.execute(
                "UPDATE app_users SET display_name=?,email=?,is_active=?,global_scope=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (display_name, email, int(active), int(global_scope), user_id),
            ).rowcount != 1:
                raise NotFound("Usuário não encontrado.")
            self._replace_access(conn, user_id, roles, group_ids, link_ids)
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL", (user_id,))

    def active_global_admins(self):
        return self._all(
            """SELECT u.id FROM app_users u JOIN user_roles r ON r.user_id=u.id
            WHERE u.is_active=1 AND u.global_scope=1 AND r.role_code='administration'"""
        )

    def set_user_password(self, user_id, password_hash, must_change):
        with self.database.connect() as conn:
            if conn.execute(
                """UPDATE app_users SET password_hash=?,must_change_password=?,failed_attempts=0,
                locked_until=NULL,password_changed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (password_hash, int(must_change), user_id),
            ).rowcount != 1:
                raise NotFound("Usuário não encontrado.")
            conn.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL", (user_id,))

    def login_failed(self, user_id, locked_until=None):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE app_users SET failed_attempts=failed_attempts+1,locked_until=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (locked_until, user_id),
            )

    def login_succeeded(self, user_id):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE app_users SET failed_attempts=0,locked_until=NULL,last_login_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (user_id,),
            )

    def create_session(self, token_hash, user_id, now, idle_expires, absolute_expires):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO auth_sessions VALUES (?,?,?,?,?,?,NULL)",
                (token_hash, user_id, now, now, idle_expires, absolute_expires),
            )

    def session(self, token_hash):
        rows = self._all("SELECT * FROM auth_sessions WHERE token_hash=?", (token_hash,))
        return rows[0] if rows else None

    def touch_session(self, token_hash, now, idle_expires):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET last_seen_at=?,idle_expires_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (now, idle_expires, token_hash),
            )

    def revoke_session(self, token_hash):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE token_hash=? AND revoked_at IS NULL",
                (token_hash,),
            )

    # Invoice template configuration.
    def template_override(self, *, group_id=None, link_id=None):
        if group_id is None and link_id is None:
            sql, params = "SELECT * FROM invoice_template_overrides WHERE group_id IS NULL AND link_id IS NULL", ()
        elif group_id is not None:
            sql, params = "SELECT * FROM invoice_template_overrides WHERE group_id=?", (group_id,)
        else:
            sql, params = "SELECT * FROM invoice_template_overrides WHERE link_id=?", (link_id,)
        rows = self._all(sql, params)
        return model(InvoiceTemplateOverride, rows[0]) if rows else None

    def save_template_override(self, value: InvoiceTemplateOverride):
        data = asdict(value)
        key = data.pop("id")
        expected_revision = data.pop("revision")
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            if key:
                changed = conn.execute(
                    """UPDATE invoice_template_overrides SET group_id=?,link_id=?,base_version=?,title_text=?,
                    payment_terms=?,observation_mode=?,observation_text=?,logo_asset=?,primary_color=?,border_color=?,
                    text_color=?,font_family=?,title_font_size=?,body_font_size=?,show_period=?,revision=revision+1,
                    updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND revision=?""",
                    (*data.values(), key, expected_revision),
                ).rowcount
                if changed != 1:
                    raise ConcurrencyError("O template foi alterado por outro usuário. Recarregue a página.")
                return key
            try:
                return conn.execute(
                    """INSERT INTO invoice_template_overrides
                    (group_id,link_id,base_version,title_text,payment_terms,observation_mode,observation_text,
                     logo_asset,primary_color,border_color,text_color,font_family,title_font_size,body_font_size,
                     show_period,updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    tuple(data.values()),
                ).lastrowid
            except sqlite3.IntegrityError:
                raise ValidationError("Já existe um template para este escopo.") from None

    def delete_template_override(self, template_id, revision):
        with self.database.connect() as conn:
            if conn.execute(
                "DELETE FROM invoice_template_overrides WHERE id=? AND revision=?", (template_id, revision)
            ).rowcount != 1:
                raise ConcurrencyError("O template foi alterado por outro usuário. Recarregue a página.")

    # Invoice sequences and immutable issuance ledger.
    def invoice_sequence(self, target_id, group=False):
        sql = (
            "SELECT * FROM invoice_sequences WHERE group_id=?"
            if group
            else "SELECT * FROM invoice_sequences WHERE link_id=?"
        )
        rows = self._all(sql, (target_id,))
        return model(InvoiceSequence, rows[0]) if rows else None

    def invoice_sequences(self):
        return [model(InvoiceSequence, row) for row in self._all("SELECT * FROM invoice_sequences ORDER BY id")]

    def save_invoice_sequence(self, value: InvoiceSequence):
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            if value.id:
                current = conn.execute("SELECT * FROM invoice_sequences WHERE id=?", (value.id,)).fetchone()
                if not current:
                    raise NotFound("Sequência não encontrada.")
                issued = conn.execute(
                    "SELECT 1 FROM invoice_issuances WHERE sequence_id=? LIMIT 1", (value.id,)
                ).fetchone()
                if issued and value.initial_value != current["initial_value"]:
                    raise ValidationError("O número inicial não pode mudar após a primeira emissão.")
                changed = conn.execute(
                    """UPDATE invoice_sequences SET prefix=?,padding=?,initial_value=?,revision=revision+1,
                    updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND revision=?""",
                    (value.prefix, value.padding, value.initial_value, value.updated_by, value.id, value.revision),
                ).rowcount
                if changed != 1:
                    raise ConcurrencyError("A sequência foi alterada por outro usuário.")
                return value.id
            try:
                return conn.execute(
                    """INSERT INTO invoice_sequences
                    (group_id,link_id,initial_value,next_value,prefix,padding,updated_by)
                    VALUES (?,?,?,?,?,?,?)""",
                    (value.group_id, value.link_id, value.initial_value, value.initial_value,
                     value.prefix, value.padding, value.updated_by),
                ).lastrowid
            except sqlite3.IntegrityError:
                raise ValidationError("Já existe uma sequência para este alvo.") from None

    def invoice_by_idempotency(self, key):
        rows = self._all("SELECT * FROM invoice_issuances WHERE idempotency_key=?", (key,))
        return rows[0] if rows else None

    def register_invoice(self, *, sequence_id, expected_value, artifact, link_ids, issuance):
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            current = conn.execute("SELECT next_value FROM invoice_sequences WHERE id=?", (sequence_id,)).fetchone()
            if not current or current["next_value"] != expected_value:
                raise ConcurrencyError("A sequência avançou durante a emissão.")
            conn.execute(
                "INSERT INTO artifacts(id,filename,sha256,size,template_version,kind) VALUES (?,?,?,?,?,?)",
                tuple(asdict(artifact).values()),
            )
            conn.executemany(
                "INSERT INTO artifact_institutions VALUES (?,?)",
                [(artifact.id, link_id) for link_id in sorted(set(link_ids))],
            )
            conn.execute(
                """INSERT INTO invoice_issuances
                (id,sequence_id,sequence_value,display_number,artifact_id,execution_id,idempotency_key,
                 issue_date,due_date,period_text,template_version,template_snapshot_json,status,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                issuance,
            )
            conn.execute("UPDATE invoice_sequences SET next_value=next_value+1 WHERE id=?", (sequence_id,))

    def invoice_ledger(self):
        return self._all(
            """SELECT i.*,s.group_id,s.link_id,g.nome AS group_name,l.nome_instituicao
            FROM invoice_issuances i JOIN invoice_sequences s ON s.id=i.sequence_id
            LEFT JOIN grupos g ON g.id=s.group_id LEFT JOIN links l ON l.id=s.link_id
            ORDER BY i.created_at DESC,i.rowid DESC"""
        )

    def void_invoice(self, issuance_id, subject, reason):
        with self.database.connect() as conn:
            if conn.execute(
                """UPDATE invoice_issuances SET status='void',voided_by=?,voided_at=CURRENT_TIMESTAMP,void_reason=?
                WHERE id=? AND status='issued'""", (subject, reason, issuance_id)
            ).rowcount != 1:
                raise ValidationError("Emissão inexistente ou já anulada.")

    def save_group(self, group: Group):
        data = asdict(group)
        key = data.pop("id")
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            try:
                if key:
                    conn.execute(
                        "UPDATE grupos SET nome=?,parent_id=?,email_contato=?,fatura_para=?,cnpj=?,cep=?,endereco=?,numero=?,cidade=?,uf=? WHERE id=?",
                        (*data.values(), key),
                    )
                else:
                    key = conn.execute(
                        "INSERT INTO grupos (nome,parent_id,email_contato,fatura_para,cnpj,cep,endereco,numero,cidade,uf) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        tuple(data.values()),
                    ).lastrowid
            except sqlite3.IntegrityError:
                raise ValidationError("Grupo duplicado ou vínculo inválido.") from None
            self._dirty(conn)
        return key

    def save_institution(self, institution: Institution):
        data = asdict(institution)
        key = data.pop("id")
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            if key:
                conn.execute(
                    "UPDATE links SET grupo_id=?,nome_instituicao=?,host_id=?,item_down_id=?,item_up_id=?,capacidade_str=?,email_contato=? WHERE id=?",
                    (*data.values(), key),
                )
            else:
                key = conn.execute(
                    "INSERT INTO links (grupo_id,nome_instituicao,host_id,item_down_id,item_up_id,capacidade_str,email_contato) VALUES (?,?,?,?,?,?,?)",
                    tuple(data.values()),
                ).lastrowid
            self._dirty(conn)
        return key

    def save_profiles(self, profiles, items):
        with UnitOfWork(self.database) as uow:
            for profile in profiles:
                data = asdict(profile)
                uow.connection.execute(
                    "INSERT INTO faturas_cadastradas (link_id,fatura_para,cnpj,cep,endereco,numero,cidade,uf,email_contato) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(link_id) DO UPDATE SET fatura_para=excluded.fatura_para,cnpj=excluded.cnpj,cep=excluded.cep,endereco=excluded.endereco,numero=excluded.numero,cidade=excluded.cidade,uf=excluded.uf,email_contato=excluded.email_contato",
                    tuple(data.values()),
                )
                self._replace_items(uow.connection, profile.link_id, items, False)

    @staticmethod
    def _replace_items(conn, target_id, items, group):
        table, key = ("itens_fatura_grupo", "grupo_id") if group else ("itens_fatura", "link_id")
        conn.execute(
            (
                "DELETE FROM itens_fatura_grupo WHERE grupo_id=?"
                if group
                else "DELETE FROM itens_fatura WHERE link_id=?"
            ),
            (target_id,),
        )
        conn.executemany(
            (
                "INSERT INTO itens_fatura_grupo (grupo_id,descricao,quantidade,valor_unitario) VALUES (?,?,?,?)"
                if group
                else "INSERT INTO itens_fatura (link_id,descricao,quantidade,valor_unitario) VALUES (?,?,?,?)"
            ),
            [(target_id, i.descricao, i.quantidade, i.valor_unitario) for i in items],
        )

    def save_items(self, target_id, items, group=False):
        with UnitOfWork(self.database) as uow:
            self._replace_items(uow.connection, target_id, items, group)

    def delete_institution(self, link_id):
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            for row in conn.execute("SELECT link_ids FROM agendamentos"):
                if link_id in json.loads(row[0]):
                    raise ValidationError("Instituição vinculada a agendamento; remova o vínculo primeiro.")
            try:
                conn.execute("DELETE FROM links WHERE id=?", (link_id,))
            except sqlite3.IntegrityError:
                raise ValidationError("Instituição possui histórico, fatura ou itens vinculados.") from None
            self._dirty(conn)

    def delete_group(self, group_id):
        with UnitOfWork(self.database) as uow:
            try:
                uow.connection.execute("UPDATE grupos SET parent_id=NULL WHERE parent_id=?", (group_id,))
                uow.connection.execute("DELETE FROM grupos WHERE id=?", (group_id,))
            except sqlite3.IntegrityError:
                raise ValidationError(
                    "Grupo possui instituições, itens ou agendamentos vinculados."
                ) from None
            self._dirty(uow.connection)

    def register_artifact(self, artifact: Artifact, ids, period_text=None):
        with UnitOfWork(self.database) as uow:
            conn = uow.connection
            conn.execute(
                "INSERT INTO artifacts(id,filename,sha256,size,template_version,kind) VALUES (?,?,?,?,?,?)",
                tuple(asdict(artifact).values()),
            )
            for link_id in set(ids):
                conn.execute("INSERT INTO artifact_institutions VALUES (?,?)", (artifact.id, link_id))
                if period_text is not None:
                    conn.execute(
                        "INSERT INTO historico_relatorios(link_id,periodo_texto,artifact_id) VALUES (?,?,?)",
                        (link_id, period_text, artifact.id),
                    )

    def artifact(self, artifact_id):
        rows = self._all("SELECT * FROM artifacts WHERE id=?", (artifact_id,))
        return model(Artifact, rows[0] if rows else None)

    def artifact_links(self, artifact_id):
        return [
            r["link_id"]
            for r in self._all(
                "SELECT link_id FROM artifact_institutions WHERE artifact_id=?", (artifact_id,)
            )
        ]

    def artifact_unknown_scope(self, artifact_id):
        return bool(
            self._all(
                "SELECT id FROM reconciliation WHERE source_table='artifact_scope' AND source_id=?",
                (artifact_id,),
            )
        )

    def save_group_profile(self, group, items=None):
        data = asdict(group)
        for key in ("id", "nome", "parent_id"):
            data.pop(key)
        with UnitOfWork(self.database) as uow:
            uow.connection.execute(
                "UPDATE grupos SET email_contato=?,fatura_para=?,cnpj=?,cep=?,endereco=?,numero=?,cidade=?,uf=? WHERE id=?",
                (*data.values(), group.id),
            )
            if items is not None:
                self._replace_items(uow.connection, group.id, items, True)

    def request_sync(self):
        with self.database.connect() as conn:
            self._dirty(conn)

    def history(self):
        return self._all("""SELECT h.*, l.nome_instituicao, g.nome AS grupo FROM historico_relatorios h
             JOIN links l ON h.link_id=l.id JOIN grupos g ON l.grupo_id=g.id ORDER BY h.data_geracao DESC, h.id DESC""")

    def schedules(self):
        result = []
        for row in self._all("SELECT * FROM agendamentos ORDER BY dia_envio,horario,id"):
            row["link_ids"] = tuple(json.loads(row["link_ids"]))
            result.append(model(Schedule, row))
        return result

    def schedule(self, schedule_id):
        return next((s for s in self.schedules() if s.id == schedule_id), None)

    @staticmethod
    def _dirty(conn):
        conn.execute(
            "UPDATE scheduler_state SET desired_revision=desired_revision+1,status='pending' WHERE id=1"
        )

    def save_schedule(self, schedule, check_conflicts=True):
        data = asdict(schedule)
        key = data.pop("id")
        data["link_ids"] = json.dumps(data["link_ids"])
        with UnitOfWork(self.database) as uow:
            conn = uow.connection

            def targets(group_id, ids):
                if not group_id:
                    return set(ids)
                return {
                    r[0]
                    for r in conn.execute(
                        """WITH RECURSIVE d(id) AS (
                    SELECT id FROM grupos WHERE id=? UNION SELECT g.id FROM grupos g JOIN d ON g.parent_id=d.id)
                    SELECT id FROM links WHERE grupo_id IN (SELECT id FROM d)""",
                        (group_id,),
                    )
                }

            wanted = targets(schedule.grupo_id, schedule.link_ids)
            if check_conflicts and schedule.ativo:
                for other in conn.execute("SELECT * FROM agendamentos WHERE ativo=1 AND id!=?", (key,)):
                    if wanted & targets(other["grupo_id"], json.loads(other["link_ids"])):
                        raise ValidationError(f"Conflito de instituições com agendamento #{other['id']}.")
            if key:
                conn.execute(
                    "UPDATE agendamentos SET link_ids=?,dia_envio=?,horario=?,incluir_fatura=?,fatura_num_prefixo=?,fatura_venc_dia=?,ativo=?,periodo_modo=?,data_inicio=?,data_fim=?,grupo_id=?,owner_id=? WHERE id=?",
                    (*data.values(), key),
                )
            else:
                key = conn.execute(
                    "INSERT INTO agendamentos (link_ids,dia_envio,horario,incluir_fatura,fatura_num_prefixo,fatura_venc_dia,ativo,periodo_modo,data_inicio,data_fim,grupo_id,owner_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(data.values()),
                ).lastrowid
            self._dirty(conn)
        return key

    def delete_schedule(self, schedule_id):
        with UnitOfWork(self.database) as uow:
            uow.connection.execute("DELETE FROM agendamentos WHERE id=?", (schedule_id,))
            self._dirty(uow.connection)

    def scheduler_state(self):
        return self._all("SELECT * FROM scheduler_state WHERE id=1")[0]

    def scheduler_synced(self, revision):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE scheduler_state SET synced_revision=?,status=CASE WHEN desired_revision=? THEN 'synced' ELSE 'pending' END WHERE id=1",
                (revision, revision),
            )

    def audit(self, subject, action, resource, outcome="success"):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO audit_events(subject,action,resource,outcome) VALUES (?,?,?,?)",
                (subject, action, str(resource), outcome),
            )

    def audit_recent(self):
        return self._all("SELECT * FROM audit_events ORDER BY id DESC LIMIT 100")

    def start_execution(self, execution_id, occurrence, owner, schedule_id=None):
        with self.database.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO executions(id,occurrence,schedule_id,owner_id,status) VALUES (?,?,?,?,'running')",
                (execution_id, occurrence, schedule_id, owner),
            )
            return cursor.rowcount == 1

    def finish_execution(self, execution_id, status, result):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE executions SET status=?,finished_at=CURRENT_TIMESTAMP,result_json=? WHERE id=?",
                (status, json.dumps(result), execution_id),
            )

    def enqueue(self, message_id, execution_id, payload):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO outbox(id,execution_id,payload) VALUES (?,?,?)",
                (message_id, execution_id, json.dumps(payload, ensure_ascii=False)),
            )

    def outbox(self, execution_id=None):
        return self._all(
            (
                "SELECT * FROM outbox WHERE execution_id=? ORDER BY rowid"
                if execution_id
                else "SELECT * FROM outbox ORDER BY rowid"
            ),
            (execution_id,) if execution_id else (),
        )

    def claim_message(self, message_id):
        with self.database.connect() as conn:
            return (
                conn.execute(
                    "UPDATE outbox SET status='sending',attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'",
                    (message_id,),
                ).rowcount
                == 1
            )

    def message_status(self, message_id, status):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE outbox SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, message_id)
            )

    def reconcile_message(self, message_id, status):
        with self.database.connect() as conn:
            changed = conn.execute(
                "UPDATE outbox SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('blocked','indeterminate')",
                (status, message_id),
            ).rowcount
            if changed != 1:
                raise ValidationError("Mensagem inexistente ou sem necessidade de reconciliação.")

    def recover_interrupted(self):
        # Called only while holding the exclusive worker lock.
        with self.database.connect() as conn:
            conn.execute("UPDATE outbox SET status='indeterminate' WHERE status='sending'")
            conn.execute(
                "UPDATE executions SET status='interrupted',finished_at=CURRENT_TIMESTAMP WHERE status='running'"
            )

    def execution_owner(self, execution_id):
        rows = self._all("SELECT owner_id FROM executions WHERE id=?", (execution_id,))
        if not rows:
            raise NotFound("Execução não encontrada.")
        return rows[0]["owner_id"]

    def executions(self):
        return self._all("SELECT * FROM executions ORDER BY started_at DESC LIMIT 100")
