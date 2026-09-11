from dataclasses import replace
import re
from sar.domain.errors import ValidationError
from sar.security import validation as v


def clean_host_name(name):
    return re.sub(r"^RG\d+\s+-\s+", "", name.replace(" -- GIGAFOR", "").replace(" -- RNP", "")).strip()


class Registrations:
    def __init__(self, repo, monitoring, policy):
        self.repo, self.monitoring, self.policy = repo, monitoring, policy

    def groups(self, identity):
        self.policy.require(identity, "registrations.read")
        return [g for g in self.repo.groups() if identity.global_scope or g.id in identity.group_ids]

    def institutions(self, identity):
        self.policy.require(identity, "registrations.read")
        return [
            i for i in self.repo.institutions() if identity.global_scope or i.id in identity.institution_ids
        ]

    def report_options(self, identity):
        self.policy.require(identity, "reports.read")
        groups = {g.id: g.nome for g in self.repo.groups()}
        return [
            (i, groups.get(i.grupo_id, "Sem Grupo"))
            for i in self.repo.institutions()
            if identity.global_scope or i.id in identity.institution_ids
        ]

    def hosts(self, identity):
        self.policy.require(identity, "registrations.write")
        # Full Zabbix inventory is administrative until a host-level scope adapter is configured.
        if not identity.global_scope:
            allowed = {i.host_id for i in self.institutions(identity)}
            return [h for h in self.monitoring.hosts() if h["hostid"] in allowed]
        return self.monitoring.hosts()

    def interfaces(self, identity, host_id):
        self.policy.require(identity, "registrations.write")
        if str(host_id) not in {h["hostid"] for h in self.hosts(identity)}:
            raise ValidationError("Host fora do inventário autorizado.")
        return self.monitoring.items(str(host_id))

    def save_group(self, identity, group):
        groups = [group.id] if group.id else []
        if group.parent_id:
            groups.append(group.parent_id)
        self.policy.require(identity, "registrations.write", group_ids=groups)
        name = v.text(group.nome, "Nome do grupo", required=True)
        if group.id:
            original = self.repo.group(group.id)
            if original.parent_id != group.parent_id:
                raise ValidationError("Alteração de hierarquia não está disponível nesta versão.")
            group = replace(original, nome=name)
        else:
            from sar.domain.models import Group

            group = Group(0, name, group.parent_id)
        if group.parent_id:
            parent = self.repo.group(group.parent_id)
            if parent.parent_id:
                raise ValidationError("Selecione um grupo raiz.")
        saved = self.repo.save_group(replace(group, nome=name))
        self.repo.audit(identity.subject, "groups.save", saved)
        return saved

    def delete_group(self, identity, group_id):
        self.policy.require(identity, "registrations.write", self.repo.group_links(group_id), [group_id])
        self.repo.delete_group(group_id)
        self.repo.audit(identity.subject, "groups.delete", group_id)

    def save_institution(self, identity, institution):
        self.policy.require(
            identity,
            "registrations.write",
            [institution.id] if institution.id else [],
            [institution.grupo_id],
        )
        v.identifier(institution.grupo_id)
        if institution.id:
            current = self.repo.institution(institution.id)
            if institution.host_id != current.host_id:
                raise ValidationError("A edição preserva o host vinculado.")
        interfaces = {i["itemid"] for i in self.interfaces(identity, institution.host_id)}
        if institution.item_down_id not in interfaces or institution.item_up_id not in interfaces:
            raise ValidationError("Selecione interfaces válidas do host.")
        updated = replace(
            institution,
            nome_instituicao=v.text(institution.nome_instituicao, "Nome", required=True),
            capacidade_str=v.text(institution.capacidade_str, "Capacidade", required=True),
            email_contato=v.email(institution.email_contato, optional=True),
        )
        saved = self.repo.save_institution(updated)
        self.repo.audit(identity.subject, "institutions.save", saved)
        return saved

    def delete_institution(self, identity, link_id):
        self.policy.require(identity, "registrations.write", [v.identifier(link_id)])
        self.repo.delete_institution(link_id)
        self.repo.audit(identity.subject, "institutions.delete", link_id)

    def profile(self, identity, link_id):
        self.policy.require(identity, "billing.read", [link_id])
        return self.repo.profile(link_id)

    def items(self, identity, target_id, group=False):
        self.policy.require(
            identity,
            "billing.read",
            self.repo.group_links(target_id) if group else [target_id],
            [target_id] if group else [],
        )
        return self.repo.invoice_items(target_id, group)

    def save_profiles(self, identity, profiles, items):
        self.policy.require(identity, "billing.write", [p.link_id for p in profiles])
        for profile in profiles:
            v.text(profile.fatura_para, "Nome para fatura", required=True)
            for field in ("cnpj", "cep", "endereco", "numero", "cidade", "uf"):
                v.text(getattr(profile, field), field)
        self.repo.save_profiles(profiles, v.items(items))
        self.repo.audit(identity.subject, "profiles.save", ",".join(str(p.link_id) for p in profiles))

    def save_group_billing(self, identity, group, items=None):
        self.policy.require(identity, "billing.write", self.repo.group_links(group.id), [group.id])
        original = self.repo.group(group.id)
        if group.nome != original.nome or group.parent_id != original.parent_id:
            raise ValidationError("O perfil comercial não pode alterar a hierarquia.")
        v.text(group.fatura_para, "Nome para fatura", required=True)
        v.email(group.email_contato)
        for field in ("cnpj", "cep", "endereco", "numero", "cidade", "uf"):
            v.text(getattr(group, field), field)
        self.repo.save_group_profile(group, v.items(items) if items is not None else None)
        self.repo.audit(identity.subject, "group-billing.save", group.id)

    def save_group_items(self, identity, group_id, items):
        self.policy.require(identity, "billing.write", self.repo.group_links(group_id), [group_id])
        self.repo.save_items(group_id, v.items(items), group=True)
        self.repo.audit(identity.subject, "group-items.save", group_id)
