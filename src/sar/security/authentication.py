from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import uuid

from sar.domain.errors import AccessDenied, ConfigurationError, ValidationError
from sar.domain.models import AppUser
from sar.security.identity import Identity
from sar.security.validation import email as validate_email, text


GENERIC_LOGIN_ERROR = "Usuário ou senha inválidos, conta inativa ou temporariamente bloqueada."


class PasswordHasher:
    """Argon2id boundary kept independent from application services and LDAP."""

    def __init__(self):
        try:
            from argon2 import PasswordHasher as ArgonHasher
            from argon2.low_level import Type
        except ImportError:
            raise ConfigurationError("Instale a dependência argon2-cffi para usar autenticação local.") from None
        self._hasher = ArgonHasher(
            time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID
        )
        self._dummy = self._hasher.hash("SAR-dummy-password-not-a-credential")

    @staticmethod
    def validate(password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise ValidationError("A senha deve ter entre 12 e 128 caracteres.")
        return password

    def hash(self, password):
        return self._hasher.hash(self.validate(password))

    def verify(self, encoded, password):
        from argon2.exceptions import InvalidHashError, VerificationError

        candidate = encoded or self._dummy
        try:
            valid = self._hasher.verify(candidate, password)
        except (VerificationError, InvalidHashError):
            return False, False
        return bool(valid and encoded), bool(encoded and self._hasher.check_needs_rehash(encoded))


class IdentityDirectory:
    """Resolves current grants for interactive sessions and background owners."""

    def __init__(self, repo):
        self.repo = repo

    def resolve(self, subject):
        user = self.repo.user(subject)
        if not user.is_active:
            raise AccessDenied("Identidade inativa.")
        roles = self.repo.user_roles(user.id)
        groups, institutions = self.repo.user_scopes(user.id)
        return Identity(
            user.id,
            roles,
            institutions,
            groups,
            bool(user.global_scope),
            user.email,
            bool(user.email),
        )


class AuthenticationService:
    idle_timeout = timedelta(minutes=30)
    absolute_timeout = timedelta(hours=8)

    def __init__(self, repo, directory, hasher):
        self.repo, self.directory, self.hasher = repo, directory, hasher

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def login(self, username, password):
        username = str(username or "").strip()
        user = self.repo.user_by_username(username) if username else None
        now = self._now()
        locked = False
        if user and user.locked_until:
            try:
                locked = datetime.fromisoformat(user.locked_until) > now
            except ValueError:
                locked = True
        valid, rehash = self.hasher.verify(user.password_hash if user else None, str(password or ""))
        if not user or not user.is_active or locked or not valid:
            if user and not locked:
                lock_until = now + timedelta(minutes=15) if user.failed_attempts + 1 >= 5 else None
                self.repo.login_failed(user.id, lock_until.isoformat() if lock_until else None)
            self.repo.audit(user.id if user else "unknown", "auth.login", "session", "denied")
            raise AccessDenied(GENERIC_LOGIN_ERROR)
        if rehash:
            self.repo.set_user_password(user.id, self.hasher.hash(password), user.must_change_password)
        self.repo.login_succeeded(user.id)
        token = secrets.token_urlsafe(32)
        self.repo.create_session(
            self._digest(token), user.id, now.isoformat(),
            (now + self.idle_timeout).isoformat(), (now + self.absolute_timeout).isoformat(),
        )
        self.repo.audit(user.id, "auth.login", "session")
        return token

    def current(self, token):
        if not token:
            raise AccessDenied("Sessão ausente ou expirada.")
        digest = self._digest(token)
        session = self.repo.session(digest)
        now = self._now()
        if not session or session["revoked_at"]:
            raise AccessDenied("Sessão ausente ou expirada.")
        if datetime.fromisoformat(session["idle_expires_at"]) <= now or datetime.fromisoformat(
            session["absolute_expires_at"]
        ) <= now:
            self.repo.revoke_session(digest)
            raise AccessDenied("Sessão ausente ou expirada.")
        absolute = datetime.fromisoformat(session["absolute_expires_at"])
        idle = min(now + self.idle_timeout, absolute)
        self.repo.touch_session(digest, now.isoformat(), idle.isoformat())
        return self.directory.resolve(session["user_id"])

    def user_for_token(self, token):
        identity = self.current(token)
        return self.repo.user(identity.subject)

    def logout(self, token):
        if token:
            self.repo.revoke_session(self._digest(token))

    def change_password(self, token, current_password, new_password):
        identity = self.current(token)
        user = self.repo.user(identity.subject)
        valid, _ = self.hasher.verify(user.password_hash, current_password)
        if not valid:
            raise AccessDenied("Senha atual inválida.")
        self.repo.set_user_password(user.id, self.hasher.hash(new_password), False)
        self.repo.audit(user.id, "auth.password.change", user.id)


class UserAdministrationService:
    def __init__(self, repo, policy, hasher):
        self.repo, self.policy, self.hasher = repo, policy, hasher

    def list(self, identity):
        self.policy.require(identity, "users.manage")
        return [
            {
                "user": user,
                "roles": self.repo.user_roles(user.id),
                "groups": self.repo.user_scopes(user.id)[0],
                "institutions": frozenset(row["link_id"] for row in self.repo._all(
                    "SELECT link_id FROM user_institution_scopes WHERE user_id=?", (user.id,)
                )),
            }
            for user in self.repo.users()
        ]

    @staticmethod
    def _username(value):
        value = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,100}", value):
            raise ValidationError("Usuário deve ter de 3 a 100 caracteres seguros.")
        return value

    def create(self, identity, username, display_name, email, roles, global_scope=False, group_ids=(), link_ids=()):
        self.policy.require(identity, "users.manage")
        roles = frozenset(roles)
        if "administration" in roles and not global_scope:
            raise ValidationError("Administração exige escopo global.")
        temporary = secrets.token_urlsafe(18)
        user = AppUser(
            uuid.uuid4().hex, self._username(username), text(display_name, "Nome", required=True),
            validate_email(email, optional=True) or None, password_hash=self.hasher.hash(temporary),
            global_scope=bool(global_scope),
        )
        self.repo.create_user(user, roles, group_ids, link_ids)
        self.repo.audit(identity.subject, "users.create", user.id)
        return user.id, temporary

    def save(self, identity, user_id, display_name, email, active, global_scope, roles, group_ids=(), link_ids=()):
        self.policy.require(identity, "users.manage")
        roles = frozenset(roles)
        if "administration" in roles and not global_scope:
            raise ValidationError("Administração exige escopo global.")
        current = self.repo.user(user_id)
        removing_admin = current.is_active and current.global_scope and "administration" in self.repo.user_roles(user_id)
        remains_admin = active and global_scope and "administration" in roles
        if removing_admin and not remains_admin and len(self.repo.active_global_admins()) <= 1:
            raise ValidationError("Não é permitido remover o último administrador global ativo.")
        self.repo.update_user_access(
            user_id, display_name=text(display_name, "Nome", required=True),
            email=validate_email(email, optional=True) or None, active=active, global_scope=global_scope,
            roles=roles, group_ids=group_ids, link_ids=link_ids,
        )
        self.repo.audit(identity.subject, "users.update", user_id)
        return True

    def reset_password(self, identity, user_id):
        self.policy.require(identity, "users.manage")
        temporary = secrets.token_urlsafe(18)
        self.repo.set_user_password(user_id, self.hasher.hash(temporary), True)
        self.repo.audit(identity.subject, "users.password.reset", user_id)
        return temporary


def trusted_cli_identity(app, username=None):
    """Resolve audit identity for commands already confined to the SAR service account."""
    if app.settings.access_mode == "internal_team":
        return app.identities.current()
    if not username:
        raise AccessDenied("Informe --as-user para executar este comando no modo local.")
    user = app.repo.user_by_username(username)
    if not user:
        raise AccessDenied("Usuário de auditoria não encontrado.")
    return app.identities.resolve(user.id)


class LdapCredentialAuthenticator:
    """Future adapter contract. LDAP credentials must only cross a validated TLS channel."""

    def authenticate(self, username, password):
        raise ConfigurationError("O provedor LDAP ainda não está configurado.")
