from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from sar.domain.errors import AccessDenied


@dataclass(frozen=True)
class Identity:
    subject: str
    roles: frozenset[str]
    institution_ids: frozenset[int] = frozenset()
    group_ids: frozenset[int] = frozenset()
    global_scope: bool = False
    email: str | None = None
    verified_email: bool = False
    expires_at: datetime | None = None


class IdentityProvider(Protocol):
    def current(self) -> Identity: ...
    def resolve(self, subject: str) -> Identity: ...


class InternalTeamProvider:
    """Explicitly enabled perimeter-trusted deployment, not LDAP authentication."""

    def current(self) -> Identity:
        return Identity("internal-team", frozenset({"administration"}), global_scope=True)

    def resolve(self, subject: str) -> Identity:
        if subject != "internal-team":
            raise AccessDenied("Responsável não reconhecido pelo provedor ativo.")
        return self.current()


def require_active(identity: Identity) -> None:
    if not identity.subject or (identity.expires_at and identity.expires_at <= datetime.now(timezone.utc)):
        raise AccessDenied("Sessão expirada ou identidade inválida.")
