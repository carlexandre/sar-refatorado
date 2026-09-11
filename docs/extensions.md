# Contratos de evolução

## LDAP

Implementar `IdentityProvider.current()` e `resolve(subject)` no adaptador corporativo, injetado pelo bootstrap. `subject` deve ser identificador estável do diretório; `email` só recebe `verified_email=True` após validação do atributo confiável. `expires_at` deve usar datetime timezone-aware.

Login usará LDAPS/StartTLS, rejeitará senha vazia e escapará filtros e DNs. Credencial de consulta virá de cofre/credencial de serviço. Senha de login terá vida limitada à autenticação; não deve ir para session_state, cache, banco, log ou jobs. Definir expiração, logout, limitação de tentativas e mensagens não enumeráveis na integração corporativa.

Mapear grupos LDAP para consultation, operations, billing e administration. Resolver hierarquia autorizada em `institution_ids` e `group_ids`; não interpretar `global_scope` a partir de formulário. Administração pode ser restrita a um escopo, exceto operações administrativas globais que devem exigir escopo global no adaptador corporativo.

O responsável do agendamento é seu `owner_id`, preservado nas edições. O worker resolve sua identidade novamente antes de executar e enviar. Um responsável inválido bloqueia a operação; e-mail ausente/inválido em identidade ainda autorizada usa a caixa institucional para Reply-To.

## Templates

Recursos empacotados em `sar/resources/templates/legacy_v1/template.json`; logos empacotados e enumerados. Overrides controlados são resolvidos por padrão, grupos ancestrais e instituição. `legacy_v1` permanece imutável; uma nova versão exige novo recurso, migração/validação e testes visuais.

`IdentityDirectory` separa credenciais de roles/escopos. Um adaptador LDAP futuro deve usar somente LDAPS/TLS com validação de certificado, identificar pessoas por atributo imutável e nunca persistir a senha recebida. Roles e escopos continuam locais até existir uma regra corporativa explícita de mapeamento de grupos LDAP.

Perfil comercial e itens permanecem no banco, separados de estilo e emissor. Não há herança automática de itens de grupo. O gerenciador futuro deve persistir vínculo com versão e snapshot de execução, sem permitir Python, HTML executável ou caminhos/URLs arbitrários.

## Semiautomação e escala

`Reports.generate`, `Invoices.generate` e `Deliveries` estão separados. O fluxo de revisão poderá gerar artefatos e mensagens pendentes antes da autorização explícita de envio. O runner é independente do Streamlit.

Para múltiplos servidores, substituir SQLite/lock de arquivo por banco transacional e mecanismo de claim/lease apropriados, mantendo interfaces e a outbox. Não mover SQLite para NFS. `submitted` significa aceito pelo relay, não entregue à caixa postal. Mesmo com broker, reconciliação de submissão SMTP ambígua permanece necessária.
