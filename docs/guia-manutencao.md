# SAR — guia de manutenção

Guia do código atual da pasta **SAR - Refatoração**, revisado em 08/10/2026. Destinado a quem vai instalar, operar ou alterar a aplicação. Os caminhos da VM descrevem a implantação conhecida; este documento não substitui uma consulta ao servidor para confirmar sua versão e estado.

## 1. O que a aplicação faz

O SAR mantém instituições, grupos e dados comerciais; consulta tráfego e eventos no Zabbix; gera relatórios técnicos e faturas em PDF; registra arquivos e emissões; agenda o envio mensal pelo Gmail.

Cada envio contém **uma fatura e um relatório**, juntos, para `svc.popce@rnp.br`, usando `svc.popce@gmail.com`. Contatos cadastrados e e-mails dos usuários não alteram essa rota. Após a aceitação SMTP e o registro local do resultado, termina o trabalho do SAR. Receber, salvar anexos e encaminhar às instituições é responsabilidade da aplicação low-code.

## 2. Como o código está organizado

```text
SAR - Refatoração/
├── app.py                 Entrada Streamlit
├── pyproject.toml         Pacote, dependências e comando sar
├── requirements*.lock     Dependências fixadas
├── .env.example           Referência de configuração sem segredos
├── src/sar/
│   ├── bootstrap.py       Monta serviços e adaptadores
│   ├── config/            Configuração
│   ├── domain/            Modelos e cálculos
│   ├── application/       Casos de uso e contratos das integrações
│   ├── infrastructure/    SQLite, Zabbix, PDFs, SMTP, arquivos e cron
│   ├── security/          Login, permissões e validação
│   ├── ui/                Telas Streamlit
│   ├── cli/               Comandos administrativos
│   ├── workers/           Execuções e sincronização do cron
│   ├── migrations/        Evolução do banco
│   └── resources/         Imagens e templates incluídos no pacote
├── deploy/                Unidades systemd, helpers e Nginx
├── tests/                 Testes automatizados
├── tools/                 Validação e manutenção do desenvolvimento
└── docs/                  Documentação
```

**Ordem sugerida de leitura:** `bootstrap.py` → `domain/models.py` → serviço da funcionalidade → adaptadores usados por ele → tela ou comando de entrada.

As telas e a CLI chamam os serviços da aplicação. Os serviços aplicam permissões, usam as regras do domínio e acionam os adaptadores. `application/ports.py` define contratos que permitem substituir integrações por implementações falsas nos testes. O domínio não depende de Streamlit. O código novo não importa a aplicação antiga.

### Entradas e configuração

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Inicia `sar.ui.main.main`; exige o pacote instalado. |
| `src/sar/bootstrap.py` | `build()` cria banco/repositório, identidades, política, armazenamento e serviços; aceita adaptadores injetados para testes. `Application.close()` fecha a integração de monitoramento. |
| `src/sar/config/settings.py` | Lê ambiente, valida modo de acesso, HTTPS, CA e fuso; deriva caminhos do banco e artifacts. |
| `src/sar/cli/main.py` | Interpreta comandos, resolve identidade administrativa e chama migração, serviços e workers. |
| `pyproject.toml` | Define `sar-reports`, versões Python aceitas, package data, entrada `sar` e configuração de pytest/Ruff. |

### Domínio: `src/sar/domain/`

| Arquivo | Responsabilidade |
| --- | --- |
| `models.py` | Estruturas de período, instituição, grupo, perfil comercial, itens, agendamento, usuário, PDF, notificação, execução, template e sequência. |
| `periods.py` | Validação de intervalos, mês anterior, competência, timestamps para consultas e vencimento. |
| `traffic.py` | Médias/picos em Mbps, escolha entre histórico e trends, alinhamento de séries, eventos e utilização da capacidade declarada. |
| `billing.py` | Montagem dos dados comerciais da fatura, totais e formatação monetária. |
| `errors.py` | Erros de validação, acesso, configuração, integração, concorrência e entrega incerta. |

### Aplicação: `src/sar/application/`

| Arquivo | Responsabilidade |
| --- | --- |
| `dto.py` | `RunRequest`: seleção, período, vencimento e parâmetros de execução. |
| `ports.py` | Contratos de monitoramento, documentos, armazenamento, notificações, segredos, agendamento e transação. |
| `services/registrations.py` | Consulta e manutenção de grupos, instituições, perfis comerciais e itens; descoberta de hosts/interfaces. |
| `services/reports.py` | Obtém dados Zabbix, calcula métricas, gera PDF, salva e registra histórico com escopo das instituições. |
| `services/invoices.py` | Prévia, emissão, sequências, livro de emissões e anulação; combina lock, template e registro transacional. |
| `services/invoice_templates.py` | Valida overrides e resolve herança do template; registra snapshot da configuração utilizada. |
| `services/schedules.py` | Elegibilidade, criação, edição, pausa e exclusão; solicita sincronização e fornece diagnóstico. |
| `services/deliveries.py` | Orquestra relatório + fatura, monta assunto/corpo, cria outbox e submete mensagens; revalida permissões do dono antes de enviar. |
| `services/history.py` | Lista histórico e autoriza download; confere integridade dos arquivos armazenados. |
| `services/recovery.py` | Lista mensagens e registra decisões de recuperação com justificativa; a reconciliação não envia e-mail. |

### Integrações: `src/sar/infrastructure/`

| Arquivo | Responsabilidade |
| --- | --- |
| `persistence/sqlite.py` | Conexões, commit/rollback, foreign keys, espera por locks e aplicação explícita das migrações; ativa WAL. |
| `persistence/repositories.py` | SQL de cadastros, usuários, sessões, templates, sequências, emissões, arquivos, agenda, execuções, outbox e auditoria. |
| `persistence/unit_of_work.py` | Contexto de transação com commit/rollback. |
| `persistence/migration.py` | Importa banco e PDFs legados para um destino inexistente, preservando a origem. |
| `persistence/migration_sql.py` | SQL utilizado na conversão do banco legado. |
| `zabbix/client.py` | Conexão autenticada e consultas de hosts, itens, histórico, trends, eventos e recuperações, com TLS validado. |
| `documents/renderer.py` | Adaptador `Documents`: transforma modelos de relatório/fatura em entradas para os renderizadores. |
| `documents/report_renderer.py` | Layout e conteúdo do relatório PDF: capa, seções, tabelas, gráficos, alertas e observação de utilização. |
| `documents/invoice_renderer.py` | Layout e conteúdo da fatura PDF conforme dados comerciais e template resolvido. |
| `documents/charts.py` | Gráfico Matplotlib de download/upload. A escala do gráfico não define a capacidade contratada. |
| `documents/templates.py` | Localiza recursos empacotados e carrega templates versionados. |
| `storage/local_artifacts.py` | Salva PDFs com identificador/hash, lê arquivos e remove arquivos ainda não registrados; restringe caminhos. |
| `email/smtp_relay.py` | Adaptador `SMTPRelay`, atualmente Gmail: MIME, validação de dois PDFs, STARTTLS, autenticação, limite SIZE e classificação de falhas. |
| `secrets/runtime_credentials.py` | Lê somente nomes de credenciais permitidos em `CREDENTIALS_DIRECTORY`, com verificação de caminho/permissões. |
| `scheduling/cron.py` | Lê/renderiza/sincroniza o crontab; gerencia apenas entradas com marcador `SAR-REFACTORED`. |

### Segurança: `src/sar/security/`

| Arquivo | Responsabilidade |
| --- | --- |
| `identity.py` | Identidade, perfis, escopos e provedor interno para transição/testes. |
| `authentication.py` | Argon2id, login, sessão, bloqueio por tentativas, troca/reset de senha, administração de usuários e identidade da CLI. O contrato LDAP existe como ponto de extensão; não é uma integração pronta. |
| `authorization.py` | Política central: perfis `consultation`, `operations`, `billing` e `administration`, combinados com escopo de grupos/instituições. |
| `validation.py` | Validação de identificadores, textos, e-mails e valores recebidos. |
| `redaction.py` | Mensagens públicas de erro e referências de diagnóstico sem expor detalhes sensíveis. |

O perfil define **quais ações** são permitidas; o escopo define **sobre quais recursos**. Esconder um botão não substitui a autorização no serviço. A CLI com `--as-user` é uma entrada administrativa confiável do servidor, não um mecanismo de login para usuários remotos.

### Interface: `src/sar/ui/`

| Arquivo | Responsabilidade |
| --- | --- |
| `main.py` | Login, troca de senha temporária, recuperação da sessão por cookie, navegação e menu da conta. |
| `theme.py` | CSS, header, seletor dark/light e persistência da preferência no cookie `sar_color_theme`. |
| `controllers/context.py` | Associa aplicação e identidade às chamadas feitas pelas telas. |
| `components/common.py` | Componentes reutilizáveis: ações, navegação, títulos, tabelas, itens comerciais e downloads. |
| `views/home.py` | Página inicial e cartões de módulos. |
| `views/registrations.py` | Formulários de grupos, instituições e dados comerciais. |
| `views/reports.py` | Seleção e geração manual de relatórios. |
| `views/invoices.py` | Emissão/prévia, templates, sequências e livro de emissões. |
| `views/automation.py` | Agendamentos, sincronização e diagnóstico de execuções/outbox. |
| `views/history.py` | Pesquisa de histórico e download dos PDFs. |
| `views/users.py` | Administração de contas, perfis, escopos e reset de senha. |

Os arquivos `__init__.py` identificam os pacotes Python; não são entradas separadas da aplicação.

### Workers, implantação e ferramentas

| Arquivo | Responsabilidade |
| --- | --- |
| `src/sar/workers/runner.py` | Executa agenda ou rotina manual; controla lock, recuperação de interrupções e chave da ocorrência agendada. |
| `src/sar/workers/schedule_reconciler.py` | Valida fuso Linux, sincroniza cron e registra revisão sincronizada. |
| `src/sar/workers/locking.py` | Exclusão mútua por arquivo para evitar operações concorrentes incompatíveis. |
| `deploy/systemd/sar-ui.service` | Mantém Streamlit em loopback, sob a conta `sar`, com credencial Zabbix. |
| `deploy/systemd/sar-worker@.service` | Executa `sar run-schedule --id %i`, com credenciais Zabbix e Gmail. |
| `deploy/systemd/sar-scheduler.service` | Reconciliação oneshot, sob `sar-cron`. |
| `deploy/systemd/sar-scheduler.timer` | Solicita reconciliação após o boot e a cada 30 segundos; não é quem dispara o envio mensal. |
| `deploy/sar-run-schedule` | Launcher chamado pelo cron; solicita ao helper privilegiado o início de um worker. |
| `deploy/sar-start-schedule` | Valida ID numérico e inicia exclusivamente `sar-worker@ID.service`. |
| `deploy/sudoers-sar` | Autoriza `sar-cron` a chamar esse helper; deve ser validado com `visudo`. |
| `deploy/provision-gmail-credential.py` | Recebe senha de aplicativo em prompt oculto e provisiona a credencial conforme a versão do systemd. |
| `deploy/systemd/gmail-encrypted-worker.conf.example` | Exemplo opcional de credencial cifrada para systemd >=250. |
| `deploy/reverse-proxy/` | Configurações Nginx: HTTPS, proxy/WebSocket e restrições de rede. Revisar certificado, domínio e sub-redes antes de instalar. |
| `tools/ci_checks.py` | Executa Ruff, pytest, Bandit e scanner; `--audit` inclui auditoria de dependências. |
| `tools/security_scan.py` | Verificações de padrões de segurança no repositório. |
| `tools/lock_dependencies.py` | Ferramenta de geração dos locks de dependências. |
| `tools/render_qa.py` | Gera PDFs/PNGs sintéticos para revisão visual. |
| `tools/verify_local_migration.py` | Verifica importação de uma cópia local do legado e se a origem permaneceu intacta; depende da pasta antiga esperada. |

## 3. O que é necessário para rodar

### Desenvolvimento no Windows

Use Python **3.12**, versão validada, Git e ambiente virtual próprio. Execute na raiz do projeto:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.lock
.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
$env:SAR_DATA_DIR = "$env:LOCALAPPDATA\SAR-dev"
$env:SAR_ACCESS_MODE = "local"
.venv\Scripts\sar migrate
.venv\Scripts\sar auth bootstrap-admin --username admin --display-name "Administrador"
.venv\Scripts\python -m streamlit run app.py
```

O bootstrap solicita senha sem mostrá-la e só cria o primeiro administrador. Para importar o legado, use [o runbook de migração](migration-runbook.md) em destino inexistente, **antes** de `migrate`. Não aponte o ambiente de desenvolvimento para o banco da produção. A instalação local permite login, cadastros e histórico; consultar Zabbix e enviar exige configurar as integrações. Cron/systemd pertencem à implantação Linux.

Cookies de sessão e tema usam `Secure`; valide a persistência no ambiente HTTPS de destino. Uma instalação local por HTTP não reproduz todas as condições do navegador em produção.

### Produção no Ubuntu

São necessários Python 3.12, venv Linux, dependências de `requirements.lock`, pacote instalado, systemd >=249, cron, sudo, Nginx, DNS/certificado HTTPS e disco local para dados. Não copie a venv do Windows.

A instalação completa, contas, permissões, helpers e credenciais estão em [deployment.md](deployment.md). O `.env.example` é apenas uma referência: **não é carregado automaticamente** e seu modo `internal_team` precisa ser substituído por `SAR_ACCESS_MODE=local` para login individual.

| Configuração | Uso |
| --- | --- |
| `SAR_DATA_DIR=/var/lib/sar` | Banco, PDFs e locks; fora de OneDrive/NFS. |
| `SAR_ACCESS_MODE=local` | Login individual e permissões. |
| `SAR_ZABBIX_URL` | Endpoint HTTPS válido do Zabbix; cadastros precisam dos IDs de host/download/upload. |
| `SAR_CA_BUNDLE` | Opcional: CA corporativa quando necessária. Não configurar um caminho inexistente. |
| `SAR_TIMEZONE=America/Fortaleza` | Deve corresponder ao fuso do sistema Linux usado pelo cron. |
| `SAR_SMTP_HOST=smtp.gmail.com` | Endpoint SMTP fixo. |
| `SAR_SMTP_PORT=587`, `SAR_SMTP_TLS=starttls` | Conexão SMTP com elevação para TLS antes do login. |
| `SAR_SMTP_USER`, `SAR_MAIL_FROM` | Ambos `svc.popce@gmail.com`. |
| `SAR_MAIL_TO=svc.popce@rnp.br` | Destinatário fixo. |
| `CREDENTIALS_DIRECTORY` | Definido pelo systemd; não escrever senha no ambiente. |

Forneça `zabbix-token` ou o par `zabbix-user`/`zabbix-password`, e `gmail-app-password` para workers. A UI não precisa da senha Gmail. No Ubuntu 22 com systemd 249, os originais ficam em `/etc/sar/credentials`, diretório root `0700` e arquivos root `0600`, e são entregues por `LoadCredential`. **São texto protegido por permissões, não cifrado em repouso**. Senhas de login SAR ficam como hashes Argon2id no banco.

A rede deve permitir acesso HTTPS ao Zabbix e saída TCP 587 para Gmail, além de DNS e serviços necessários. O navegador acessa HTTPS/Nginx; Streamlit permanece em `127.0.0.1:8501`.

### Caminhos da implantação conhecida

| Caminho/conta | Finalidade |
| --- | --- |
| VM `10.85.3.180`, SSH `popce` | Administração do servidor. |
| `/opt/sar` | Projeto e venv Linux. |
| `/opt/sar/.venv/lib/python3.12/site-packages/sar` | Pacote instalado utilizado pela venv; editar apenas `src` pode não alterar o código efetivamente executado. |
| `/var/lib/sar/sar.db` | Banco de produção. |
| `/var/lib/sar/artifacts` | PDFs gerados. |
| `/etc/sar/sar.env` | Configuração não secreta recebida pelas unidades. |
| `/etc/sar/credentials` | Originais das credenciais protegidas pelo root. |
| `/etc/sar/tls` | Certificado e chave do Nginx. |
| `sar` / `sar-cron` | Execução da UI/workers / reconciliação do crontab. |

Para futuras versões, prefira instalar o pacote e conferir a versão efetiva. Scripts temporários de correções enviados à VM durante o suporte não são dependências do produto nem substituem os arquivos versionados em `deploy/`.

## 4. Fluxos que o mantenedor precisa entender

### Relatório e fatura

1. A tela/CLI fornece seleção e identidade ao serviço.
2. `Reports` consulta histórico Zabbix e recorre a trends quando o histórico não cobre o período; prepara métricas/eventos/séries e chama `Documents`.
3. O PDF é salvo em artifacts e registrado com instituições e hash para controle de acesso/integridade.
4. `Invoices` resolve template e sequência, gera o PDF e registra a emissão/número de forma transacional. Prévia não equivale à emissão.

A utilização compara o maior pico de entrada/saída com a **capacidade declarada**, convertida para Mbps. `986,41 Mbps / 10 Gbps` representa aproximadamente **9,86%**. O domínio classifica >=90% como crítico, >=75% como alto; capacidade inválida fica desconhecida. A escala visual do gráfico não entra nesse cálculo.

Templates são resolvidos na ordem padrão → grupos ancestrais → grupo/instituição aplicável. **Herdar** deixa o campo usar a configuração anterior da cadeia. A emissão guarda snapshot para que futuras alterações não mudem o documento já emitido.

O número inicial da sequência pode ser corrigido antes da primeira emissão, atualizando também o próximo número. Depois de emitir, a regra impede alterar o número inicial. Emissões manuais e automáticas compartilham a sequência; anular não significa reutilizar o número.

### Agendamento e envio

```text
UI salva agenda no SQLite e incrementa revisão desejada
  → timer systemd chama reconciliador
  → reconciliador atualiza crontab de sar-cron
  → cron chama sar-run-schedule no dia/horário
  → helper inicia sar-worker@ID
  → runner valida agenda/dono e obtém lock
  → Deliveries gera os dois PDFs e cria outbox
  → SMTPRelay autentica e submete ao Gmail
  → resultado local e encerramento
```

O timer de 30 segundos **sincroniza alterações**. O cron executa a agenda mensal. Horários já passados não são executados retroativamente pela sincronização; agendar depois do horário pode levar à próxima ocorrência mensal. Dias inexistentes no mês também precisam ser considerados ao configurar a agenda.

A ocorrência agendada tem chave baseada em ID, mês, dia e horário para evitar repetição da mesma ocorrência. Uma execução manual cria uma ocorrência nova e **pode emitir outra fatura e consumir outro número**. Não use envio manual como simples diagnóstico.

Para enviar, o cadastro precisa de dados Zabbix válidos, perfil/itens comerciais aplicáveis, sequência configurada, dono ativo com permissões, agenda ativa e sincronizada, credenciais e rede disponíveis. Em grupos, instituições sem dados podem ser omitidas do relatório; a execução registra `partial_report`. Consulte erros mesmo quando PDFs foram gerados.

O assunto/corpo é montado em `Deliveries._message()`:

```text
[SAR] - Fatura e Relatório Consolidado — Nome da instituição/grupo

Olá, equipe Nome da instituição/grupo,

Segue em anexo a Fatura Comercial consolidada e o Relatório Técnico de Monitoramento referente a 01/09/2026 a 30/09/2026.

A fatura possui vencimento para o dia 15/10/2026.

Em caso de dúvidas, nossa equipe do PoP-CE está à disposição.
```

### Outbox e recuperação

| Estado da mensagem | Interpretação |
| --- | --- |
| `pending` | Aguardando tentativa. |
| `sending` | Tentativa assumida; uma interrupção exige recuperação conservadora. |
| `submitted` com `smtp_accepted_at` | Gmail aceitou via SMTP; não prova recebimento, leitura ou encaminhamento. |
| `blocked` | Validação, permissão, autenticação, TLS ou rejeição impediram envio. |
| `indeterminate` | Pode ter havido aceitação sem confirmação local; investigar antes de reenviar. |
| `cancelled` | Cancelamento registrado por reconciliação. |

Execuções têm resultado próprio (`running`, `completed`, `partial`, `failed`, `interrupted`); `duplicate` indica uma ocorrência agendada já registrada. Não confundir execução com estado da mensagem. Não há acompanhamento da caixa de entrada nem retry automático de mensagens bloqueadas/incertas. `reconcile-message` registra uma decisão auditada, mas não inventa um timestamp de aceitação Gmail.

### Login e preferência visual

Sessões têm **30 minutos de inatividade** e limite absoluto de **8 horas**. A atividade validada renova a janela de inatividade até esse limite. O cookie `sar_session_token` compartilha o token entre abas; a validade permanece controlada no banco. Tema dark/light usa `sar_color_theme`, com duração de até um ano. Logout, expiração e revogação da sessão exigem novo login.

## 5. Banco, arquivos e migrações

| Migração | Conteúdo |
| --- | --- |
| `src/sar/migrations/001_initial.sql` | Cadastros, perfis/itens, artifacts/histórico, agendas, scheduler, execuções, outbox, reconciliação e auditoria. |
| `002_auth_templates_invoice_sequences.sql` | Usuários, papéis/escopos, sessões, overrides de templates, sequências e emissões. |
| `003_gmail_submission.sql` | Campo `smtp_accepted_at` na outbox. |

`schema_migrations` controla a versão. Migrações são explícitas por `sar migrate`, sem integração externa. Adicione novos scripts numerados; não reescreva migrações aplicadas para mudar produção. As pastas `migrations/` e `resources/` na raiz orientam o leitor: as fontes empacotadas estão em `src/sar/`.

Banco e artifacts formam um conjunto: copiar só o banco perde os PDFs; copiar só PDFs perde permissões, histórico e numeração. Para backup consistente, interrompa escritores e use backup SQLite, ou uma estratégia consistente que trate WAL corretamente, além de copiar artifacts. Proteja também configuração, credenciais e chaves TLS separadamente. O SAR não elimina relatórios antigos automaticamente.

## 6. Diagnóstico e manutenção

Leituras usuais no servidor, sem disparar envio:

```sh
sudo systemctl status sar-ui.service sar-scheduler.timer cron --no-pager
sudo systemctl list-timers sar-scheduler.timer --all --no-pager
sudo journalctl -u sar-scheduler.service -n 60 --no-pager
sudo journalctl -u sar-worker@1.service -n 60 --no-pager
sudo crontab -u sar-cron -l
```

O reconciliador e o worker são serviços `oneshot`: `inactive` após terminar com sucesso é normal. Confira timer, resultado e logs. Com ambiente da aplicação e identidade administrativa configurados, `sar diagnostics --as-user admin` e `sar outbox-list --as-user admin` mostram estado; a tela Automação → Diagnóstico também mostra execuções/outbox.

| Sintoma | Onde começar |
| --- | --- |
| 403 Nginx | Configuração ativa de `allow`/`deny`, IP real do cliente e logs Nginx. |
| Lentidão ao gerar PDF | Consultas/rede Zabbix, tamanho do período, logs, CPU/disco e locks; geração é síncrona no processo que a solicitou. |
| Agenda sincronizada, sem execução | Hora de criação vs horário cron, fuso, serviço cron, crontab e launcher/helper. |
| Execução `partial` | Lista de erros; fatura ausente, relatório parcial ou outbox bloqueada/incerta. |
| Gmail timeout | Saída TCP 587 e resolução DNS; STARTTLS/login só podem ser testados depois da conexão. |
| Gmail aceitou, mensagem não chegou | Investigar destinatário/low-code usando Message-ID; evitar reenvio indiscriminado. |
| Volta ao login | Inatividade, limite absoluto, cookie/HTTPS, logout ou revogação; não ampliar prazo para mascarar falha. |
| Mudança no fonte não aparece | Conferir pacote da venv realmente usado, instalar a versão correta e reiniciar processos. |

Para atualizar: revisar diff → validar testes → backup → parar escritores → instalar pacote Linux → aplicar migrações necessárias → validar configuração/unidades → reiniciar e conferir saúde/logs. A instalação de código não deve substituir o banco existente. Detalhes e retorno estão nos runbooks abaixo.

## 7. Como alterar e validar

| Alteração | Arquivos principais |
| --- | --- |
| Assunto/corpo do e-mail | `application/services/deliveries.py`, teste `integration/test_gmail_deliveries.py`. |
| Transporte SMTP/TLS/credencial | `infrastructure/email/smtp_relay.py`, `config/settings.py`, `secrets/runtime_credentials.py`, unidades e testes de segurança Gmail. |
| Regras de capacidade/tráfego | `domain/traffic.py`, `documents/report_renderer.py`, testes unitários e PDFs de QA. |
| Layout de fatura | `documents/invoice_renderer.py`, `documents/templates.py`, resources e testes de templates. |
| Numeração de fatura | `services/invoices.py`, `persistence/repositories.py`, migração se necessária e testes de concorrência/idempotência. |
| Agenda/cron | `services/schedules.py`, workers, `scheduling/cron.py`, deploy e testes de serviços. |
| Login/permissões | `security/`, `ui/main.py`, persistência e testes de segurança/autenticação. |
| Tela/tema | `ui/views/`, `ui/components/common.py`, `ui/theme.py`, testes UI. |

Testes usam integrações falsas e dados sintéticos. Execute dentro da venv:

```sh
python -m pytest -q
python -m ruff check src tests tools app.py
python -m bandit -r src -ll
python tools/security_scan.py
# Ou o conjunto acima:
python tools/ci_checks.py
```

| Pasta/arquivo de testes | Cobertura principal |
| --- | --- |
| `unit/test_domain.py` | Períodos, métricas e regras puras. |
| `integration/test_services.py` | Casos de uso e persistência. |
| `integration/test_auth_templates_invoices.py` | Login, templates, sequências e emissões. |
| `integration/test_gmail_deliveries.py` | Rota fixa, dois anexos, assunto/corpo e registro do envio. |
| `integration/test_recovery.py` | Outbox, interrupções e reconciliação. |
| `integration/test_migration.py` | Conversão do legado e integridade. |
| `security/test_architecture.py`, `test_boundaries.py` | Separação de camadas e limites de acesso. |
| `security/test_credentials_and_tls.py`, `test_gmail_smtp.py` | Credenciais, TLS e comportamento SMTP. |
| `ui/test_pages.py`, `test_theme.py` | Telas e apresentação. |
| `characterization/test_legacy.py` | Comparação com o comportamento/documentos legados. |
| `conftest.py` | Fixtures, banco temporário e adaptadores falsos compartilhados. |

Testes simulados não validam firewall, Gmail real, certificado/Nginx ou cron/systemd da VM. Uma validação de envio real precisa ser autorizada, pois gera documentos, pode consumir numeração e envia uma mensagem.

## 8. Documentos complementares

- [Implantação e credenciais Linux](deployment.md): instalação, permissões, serviços e Gmail.
- [Contrato de comportamento](behavior-contract.md): regras que as mudanças devem preservar.
- [Segurança](security-design.md): identidade, permissões e limites das integrações.
- [Migração e retorno](migration-runbook.md): passagem do legado e recuperação.
- [Extensões](extensions.md): como adicionar/substituir integrações.
- [Validação](validation.md): verificações do desenvolvimento.
- [Auditoria SMTP de 08/10/2026](audits/2026-10-08-smtp-vm.md): registro histórico da investigação de rede; não representa disponibilidade atual.

Ao mudar um fluxo, atualize este guia e o documento específico correspondente junto com o código.
