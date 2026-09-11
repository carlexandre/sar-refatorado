import argparse
from dataclasses import asdict
import json
import getpass
import uuid
from pathlib import Path
from sar.config.settings import Settings
from sar.security.redaction import public_error


def parser():
    root = argparse.ArgumentParser(description="SAR — relatórios e automações")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Inicializa ou migra explicitamente o banco")
    auth = commands.add_parser("auth", help="Administra o provedor local")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    bootstrap = auth_commands.add_parser("bootstrap-admin", help="Cria o primeiro administrador local")
    bootstrap.add_argument("--username", required=True)
    bootstrap.add_argument("--display-name", required=True)
    bootstrap.add_argument("--email", default="")
    bootstrap.add_argument("--claim-legacy-schedules", action="store_true")
    imp = commands.add_parser("import-legacy", help="Importa banco legado para destino inexistente")
    imp.add_argument("--source", type=Path, required=True)
    imp.add_argument("--source-artifacts", type=Path, required=True)
    sync = commands.add_parser("sync-cron")
    sync.add_argument("--launcher", type=Path, required=True)
    scheduled = commands.add_parser("run-schedule")
    scheduled.add_argument("--id", type=int, required=True)
    diagnostics = commands.add_parser("diagnostics")
    diagnostics.add_argument("--as-user")
    outbox_list = commands.add_parser("outbox-list")
    outbox_list.add_argument("--as-user")
    recovery = commands.add_parser("reconcile-message")
    recovery.add_argument("--id", required=True)
    recovery.add_argument("--decision", choices=["submitted", "retry", "cancelled"], required=True)
    recovery.add_argument("--reason", required=True)
    recovery.add_argument("--as-user")
    dispatch = commands.add_parser("dispatch-pending")
    dispatch.add_argument("--execution-id", required=True)
    dispatch.add_argument("--as-user")
    monthly = commands.add_parser("monthly", help="Rotina mensal; sem seleção processa perfis individuais")
    selection = monthly.add_mutually_exclusive_group()
    selection.add_argument("--link-ids", help="Array JSON de IDs")
    selection.add_argument("--grupo-id", type=int)
    monthly.add_argument("--incluir-fatura", action="store_true")
    monthly.add_argument("--fatura-venc-dia", type=int, default=15)
    monthly.add_argument("--data-inicio")
    monthly.add_argument("--data-fim")
    monthly.add_argument("--as-user")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    app = None
    try:
        settings = Settings.from_env()
        if args.command == "migrate":
            from sar.infrastructure.persistence.sqlite import initialize

            initialize(settings.database_path)
            print("Banco inicializado; nenhuma integração externa foi acionada.")
            return 0
        if args.command == "import-legacy":
            from sar.infrastructure.persistence.migration import import_legacy

            result = import_legacy(
                args.source, settings.database_path, args.source_artifacts, settings.artifact_dir
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "auth" and args.auth_command == "bootstrap-admin":
            from sar.domain.errors import ValidationError
            from sar.domain.models import AppUser
            from sar.infrastructure.persistence.repositories import Repository
            from sar.infrastructure.persistence.sqlite import Database
            from sar.security.authentication import PasswordHasher, UserAdministrationService
            from sar.security.validation import email, text

            repo = Repository(Database(settings.database_path))
            if repo.users():
                raise ValidationError("O administrador inicial já foi criado.")
            password = getpass.getpass("Senha inicial: ")
            confirmation = getpass.getpass("Confirme a senha: ")
            if password != confirmation:
                raise ValidationError("As senhas não coincidem.")
            user = AppUser(
                uuid.uuid4().hex, UserAdministrationService._username(args.username),
                text(args.display_name, "Nome", required=True),
                email(args.email, optional=True) or None, password_hash=PasswordHasher().hash(password),
                must_change_password=False, global_scope=True,
            )
            repo.create_user(user, {"administration"})
            if args.claim_legacy_schedules:
                with repo.database.connect() as conn:
                    conn.execute(
                        "UPDATE agendamentos SET owner_id=? WHERE owner_id='internal-team'", (user.id,)
                    )
            repo.audit(user.id, "auth.bootstrap-admin", user.id)
            print("Administrador local criado com sucesso.")
            return 0
        from sar.bootstrap import build

        app = build(settings)
        from sar.security.authentication import trusted_cli_identity
        if args.command in {"outbox-list", "reconcile-message"}:
            from sar.application.services.recovery import Recovery
            from sar.workers.locking import exclusive_lock

            service = Recovery(app.repo, app.policy)
            if args.command == "outbox-list":
                print(json.dumps(service.messages(trusted_cli_identity(app, args.as_user)), indent=2))
            else:
                with exclusive_lock(settings.data_dir / "locks" / "worker.lock"):
                    service.reconcile(
                        trusted_cli_identity(app, args.as_user), args.id, args.decision, args.reason
                    )
                print("Decisão registrada; nenhum e-mail foi enviado por este comando.")
        elif args.command == "dispatch-pending":
            from sar.workers.locking import exclusive_lock

            app.policy.require(trusted_cli_identity(app, args.as_user), "admin.diagnostics")
            with exclusive_lock(settings.data_dir / "locks" / "worker.lock"):
                app.repo.recover_interrupted()
                print(json.dumps(app.deliveries.dispatch(args.execution_id)))
        elif args.command == "sync-cron":
            from sar.infrastructure.scheduling.cron import CronScheduler
            from sar.workers.schedule_reconciler import reconcile

            reconcile(app, CronScheduler(args.launcher))
            print("Agendamentos sincronizados.")
        elif args.command == "run-schedule":
            from sar.workers.runner import run_schedule

            result = run_schedule(app, args.id)
            print(json.dumps(asdict(result)))
            return 0 if result.status in {"completed", "duplicate"} else 2
        elif args.command == "monthly":
            from sar.application.dto import RunRequest
            from sar.domain.errors import ValidationError
            from sar.security.validation import identifier
            from sar.workers.runner import run_manual

            ids = json.loads(args.link_ids) if args.link_ids else []
            if not isinstance(ids, list) or (args.link_ids is not None and not ids):
                raise ValidationError("--link-ids deve conter um array não vazio.")
            ids = tuple(identifier(i) for i in ids)
            request = RunRequest(
                link_ids=ids, group_id=args.grupo_id, include_invoice=args.incluir_fatura,
                invoice_due_day=args.fatura_venc_dia, start=args.data_inicio, end=args.data_fim,
            )
            result = run_manual(app, request, trusted_cli_identity(app, args.as_user))
            print(json.dumps(asdict(result)))
            return 0 if result.status == "completed" else 2
        elif args.command == "diagnostics":
            print(json.dumps(app.schedules.diagnostics(
                trusted_cli_identity(app, args.as_user)
            ), indent=2))
        return 0
    except Exception as error:
        print(public_error(error))
        return 1
    finally:
        if app:
            app.close()


if __name__ == "__main__":
    raise SystemExit(main())
