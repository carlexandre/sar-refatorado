# Desenho de segurança

## Fronteiras de confiança

UI → serviços autorizados → repositórios/adaptadores. Workers reutilizam serviços; parâmetros do cron se limitam a identificadores. Banco e arquivos de runtime são confiados apenas aos usuários de serviço. SQLite não oferece isolamento por usuário de aplicação: não conceder acesso direto ao banco a operadores finais.

A política de autorização nega roles desconhecidas, identidades expiradas e recursos fora do escopo. Downloads de PDFs consolidados verificam todas as instituições associadas. Faturas exigem `billing.read`, mesmo quando seu ID é conhecido por quem consulta relatórios. Documentos legados com escopo incompleto exigem administração global até reconciliação.

O modo de produção `local` autentica contas individuais. Senhas usam Argon2id com salt, bloqueio temporário após cinco falhas e redefinição administrativa obrigando troca. Tokens aleatórios têm somente seu SHA-256 persistido; sessões expiram por inatividade e prazo absoluto e são revogadas após mudanças de senha ou privilégio. `InternalTeamProvider` permanece apenas como compatibilidade explícita para testes/transição e não autentica pessoas.

Roles são uma allowlist do código e suas atribuições/escopos ficam no SQLite. Templates, sequências, anulações e usuários exigem administração global. A interface oculta rotas não permitidas, mas todo serviço repete a autorização; URLs e IDs conhecidos não contornam RBAC.

## Segredos e TLS

Credenciais de execução provêm de `CREDENTIALS_DIRECTORY`; no Linux, arquivos com leitura para grupo/outros são recusados. Systemd `LoadCredentialEncrypted` decripta o segredo para a unidade em runtime. O cofre corporativo poderá provisionar essas credenciais; a chave não fica ao lado do código. Senhas de usuário LDAP nunca serão utilizadas para SMTP.

Zabbix usa somente HTTPS, timeout de 30 segundos e no máximo uma repetição de consulta de leitura após erro transitório de rede. Autenticação e erro TLS não são repetidos. A conta/token precisa ser limitada a leitura pela administração do Zabbix; o software não cria essa permissão no servidor.

SMTP usa TLS implícito ou StartTLS obrigatório, hostname e CA validados. Não há `login()`. O relay precisa restringir origem/remetente e não pode ser aberto. SPF, DKIM e DMARC são responsabilidade do domínio corporativo; Reply-To não garante entregabilidade.

## Dados e operação

Valores SQL são parametrizados. Consultas de runtime são literais; importação usa whitelist de tabelas e colunas. Entradas LDAP futuras exigirão escape específico para filtro e DN, nunca interpolação direta.

Artifacts têm UUID, SHA-256, tamanho e versão de template; paths são confinados à raiz, symlinks de arquivo recusados e Linux usa `O_NOFOLLOW`. Escrita temporária, fsync e rename evitam documentos parciais. Diretório de artifacts não é compartilhado com usuários finais. Uma queda abrupta pode deixar arquivo sem registro; preservá-lo para reconciliação, sem removê-lo automaticamente.

SQLite habilita foreign_keys em cada conexão e usa transações curtas. Código não inicializa banco ao importar. Outbox e execuções persistem em SQLite; lock de processo serializa workers. Após interrupção, `sending` torna-se `indeterminate`; pendências não são reenviadas sem comando operacional explícito.

Emissões manuais e workers compartilham um lock exclusivo. O próximo número, artifact e livro de emissões são confirmados por `BEGIN IMMEDIATE` e restrições `UNIQUE`; falhas anteriores ao commit não consomem número. Anulações preservam o registro, o número e o PDF. Cada emissão armazena o snapshot efetivo do template.

Código instalado é somente leitura. UI e worker rodam como `sar`; reconciliador como `sar-cron`, com acesso somente ao grupo de serviço do banco. Essas contas têm acesso privilegiado aos dados da aplicação e não constituem um ambiente mutuamente hostil. O único helper elevado inicia uma unidade systemd fixa com ID numérico validado.

Logs públicos contêm códigos e IDs, sem stacktrace ou texto de erro de provedores. A auditoria registra ator, ação, recurso e resultado. Ela não é inviolável contra administradores do banco; para esse requisito, encaminhar eventos a coletor corporativo imutável. Criptografia em repouso e de backups é fornecida pelo volume/serviço corporativo, não por criptografia caseira no Python.

## Controles de verificação

Pytest verifica isolamento, caminhos, e-mail, TLS, cron, transações, migração e equivalência. Ruff verifica o código. Bandit faz análise estática de produção. `security_scan.py` bloqueia padrões básicos de segredos embutidos e APIs explicitamente proibidas; não substitui um scanner corporativo de histórico Git. `pip-audit` exige rede para consultar vulnerabilidades e seu resultado deve ser registrado a cada release.
