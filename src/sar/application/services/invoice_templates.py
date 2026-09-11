from dataclasses import asdict, replace
import re

from sar.domain.errors import ValidationError
from sar.domain.models import InvoiceTemplateOverride, ResolvedInvoiceTemplate
from sar.infrastructure.documents.templates import load_template
from sar.security.validation import text


ALLOWED_LOGOS = {"gigafor-logo.png", "pop-ce-logo-preto.png", "rnp-logo-preto.png"}
ALLOWED_FONTS = {"Arial", "Helvetica", "Times", "Courier"}
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


class InvoiceTemplateService:
    def __init__(self, repo, policy):
        self.repo, self.policy = repo, policy

    @staticmethod
    def _base():
        resource = load_template("legacy_v1")
        return ResolvedInvoiceTemplate(
            title_text=resource["issuer"]["title"],
            payment_terms=resource["issuer"]["payment_terms"],
        )

    @staticmethod
    def _apply(resolved, override):
        changes = {}
        for field in (
            "base_version", "title_text", "payment_terms", "logo_asset", "primary_color",
            "border_color", "text_color", "font_family", "title_font_size", "body_font_size", "show_period",
        ):
            value = getattr(override, field)
            if value is not None:
                changes[field] = value
        if override.observation_mode == "show":
            changes["show_observation"] = True
            changes["observation_text"] = override.observation_text or ""
        elif override.observation_mode == "hide":
            changes["show_observation"] = False
            changes["observation_text"] = ""
        return replace(resolved, **changes)

    def resolve(self, identity, target_id, *, group=False):
        ids = self.repo.group_links(target_id) if group else [target_id]
        group_ids = [target_id] if group else []
        self.policy.require(identity, "billing.template.read", ids, group_ids)
        resolved = self._base()
        default = self.repo.template_override()
        if default:
            resolved = self._apply(resolved, default)
        if group:
            ancestry = self.repo.group_ancestors(target_id)
        else:
            institution = self.repo.institution(target_id)
            ancestry = self.repo.group_ancestors(institution.grupo_id)
        for group_id in ancestry:
            override = self.repo.template_override(group_id=group_id)
            if override:
                resolved = self._apply(resolved, override)
        if not group:
            override = self.repo.template_override(link_id=target_id)
            if override:
                resolved = self._apply(resolved, override)
        return resolved

    def resolve_default(self, identity):
        self.policy.require(identity, "billing.template.read")
        resolved = self._base()
        default = self.repo.template_override()
        return self._apply(resolved, default) if default else resolved

    def get_override(self, identity, *, group_id=None, link_id=None):
        ids = self.repo.group_links(group_id) if group_id else ([link_id] if link_id else [])
        self.policy.require(identity, "billing.template.read", ids, [group_id] if group_id else [])
        return self.repo.template_override(group_id=group_id, link_id=link_id)

    @staticmethod
    def validate(value):
        if value.group_id is not None and value.link_id is not None:
            raise ValidationError("Escolha grupo ou instituição, não ambos.")
        if value.base_version not in (None, "legacy_v1"):
            raise ValidationError("Versão de template não suportada.")
        if value.observation_mode not in {"inherit", "show", "hide"}:
            raise ValidationError("Modo de observação inválido.")
        for name in ("title_text", "payment_terms", "observation_text"):
            candidate = getattr(value, name)
            if candidate is not None:
                text(candidate, name, limit=4000)
                if "<" in candidate or ">" in candidate:
                    raise ValidationError("HTML não é permitido em templates.")
        if value.logo_asset is not None and value.logo_asset not in ALLOWED_LOGOS:
            raise ValidationError("Logo não permitido.")
        if value.font_family is not None and value.font_family not in ALLOWED_FONTS:
            raise ValidationError("Fonte não permitida.")
        for name in ("primary_color", "border_color", "text_color"):
            candidate = getattr(value, name)
            if candidate is not None and not COLOR.fullmatch(candidate):
                raise ValidationError("Cor deve usar o formato hexadecimal #RRGGBB.")
        return value

    def save(self, identity, value: InvoiceTemplateOverride):
        ids = self.repo.group_links(value.group_id) if value.group_id else ([value.link_id] if value.link_id else [])
        self.policy.require(identity, "billing.template.write", ids, [value.group_id] if value.group_id else [])
        value = replace(self.validate(value), updated_by=identity.subject)
        saved = self.repo.save_template_override(value)
        self.repo.audit(identity.subject, "billing.template.save", saved)
        return saved

    def discard(self, identity, template_id, revision, *, group_id=None, link_id=None):
        ids = self.repo.group_links(group_id) if group_id else ([link_id] if link_id else [])
        self.policy.require(identity, "billing.template.write", ids, [group_id] if group_id else [])
        self.repo.delete_template_override(template_id, revision)
        self.repo.audit(identity.subject, "billing.template.delete", template_id)
        return True

    @staticmethod
    def snapshot(value):
        return asdict(value)
