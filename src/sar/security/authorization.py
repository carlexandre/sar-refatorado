from sar.domain.errors import AccessDenied
from sar.security.identity import Identity, require_active


PERMISSIONS = {
    "consultation": {"reports.read"},
    "operations": {"reports.read", "reports.generate", "registrations.read", "registrations.write"},
    "billing": {
        "reports.read",
        "reports.generate",
        "registrations.read",
        "billing.read",
        "billing.write",
        "billing.issue",
        "billing.template.read",
        "billing.sequence.read",
        "billing.ledger.read",
        "schedules.read",
        "schedules.write",
        "deliveries.send",
    },
    "administration": {"*"},
}


class AuthorizationPolicy:
    def allows(self, identity: Identity, action: str, institution_ids=(), group_ids=()) -> bool:
        try:
            self.require(identity, action, institution_ids, group_ids)
            return True
        except AccessDenied:
            return False

    def require(self, identity: Identity, action: str, institution_ids=(), group_ids=()) -> None:
        require_active(identity)
        if action.startswith("admin.") and not identity.global_scope:
            raise AccessDenied("Ação administrativa global exige escopo global.")
        permissions = set().union(*(PERMISSIONS.get(role, set()) for role in identity.roles))
        if action not in permissions and "*" not in permissions:
            raise AccessDenied("Você não possui permissão para esta ação.")
        if not identity.global_scope and (
            not set(institution_ids) <= identity.institution_ids or not set(group_ids) <= identity.group_ids
        ):
            raise AccessDenied("Recurso fora do seu escopo de acesso.")
