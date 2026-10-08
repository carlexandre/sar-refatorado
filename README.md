# SAR — versão refatorada

Monólito modular Python: Streamlit apresenta as telas; os serviços executam as regras; adaptadores implementam SQLite, Zabbix, documentos, arquivos e SMTP Gmail. Workers e CLI usam os mesmos serviços.

A versão original permanece separada. Nenhum módulo legado é importado pela aplicação nova. A aplicação oferece login local, RBAC, templates de fatura herdáveis e numeração transacional. O contrato de identidade está preparado para um adaptador LDAP posterior.

Comece pelo [Guia de manutenção](docs/guia-manutencao.md): requisitos, mapa dos módulos, fluxos e diagnóstico para novos mantenedores.

## Instalação local

Python 3.12 é a versão validada. No diretório desta versão:

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

`migrate` inicializa um banco vazio. Para importar o banco antigo, **não execute migrate antes de import-legacy**: a importação exige destino inexistente.

```powershell
.venv\Scripts\sar import-legacy --source "CAMINHO\relatorios_popce.db" --source-artifacts "CAMINHO\pdfs_gerados"
```

Em Linux, use `.venv/bin/python` e `.venv/bin/sar`. Para produção, instale `requirements.lock`, ferramentas de build fixadas de `requirements-dev.lock`, e o pacote com `--no-deps`. Mantenha código somente leitura e dados em disco local fora da pasta do projeto. Veja [implantação](docs/deployment.md).

## Configuração

`.env.example` documenta apenas variáveis não secretas; **não há carregamento automático de `.env`**. O processo precisa recebê-las do ambiente ou `EnvironmentFile` do systemd.

- `SAR_DATA_DIR`: obrigatório; banco, artifacts e locks. Nunca usar OneDrive/NFS em produção.
- `SAR_ACCESS_MODE=local`: login com senha Argon2id, sessões revogáveis e RBAC no SQLite. `internal_team` permanece somente para transição/testes em perímetro confiável; não autentica pessoas.
- `SAR_ZABBIX_URL`: URL HTTPS sem credenciais; `SAR_CA_BUNDLE`: CA corporativa, quando necessária. Sem CA configurada, aplica-se a cadeia de confiança padrão, nunca `verify=False`.
- `CREDENTIALS_DIRECTORY`: fornecido pelo systemd; contém `zabbix-token` ou `zabbix-user` e `zabbix-password`, e `gmail-app-password` nos workers. Segredos não são copiados do `.env` legado.
- `SAR_SMTP_HOST=smtp.gmail.com`, `SAR_SMTP_PORT=587`, `SAR_SMTP_TLS=starttls`: autenticação Gmail após TLS.
- `SAR_SMTP_USER=svc.popce@gmail.com`, `SAR_MAIL_FROM=svc.popce@gmail.com`, `SAR_MAIL_TO=svc.popce@rnp.br`: rota fixa validada pelo adaptador. Sem CC/BCC ou Reply-To de usuário.
- `gmail-app-password`: senha de aplicativo lida somente de `CREDENTIALS_DIRECTORY`; não há senha SMTP em código, `.env` ou variável de ambiente.
- `SAR_TIMEZONE=America/Fortaleza`: o fuso do servidor cron deve ser o mesmo.

Sem Zabbix configurado, consultas falham de forma segura; cadastros existentes e histórico continuam disponíveis. Sem credencial Gmail, os documentos continuam sendo gerados e as mensagens ficam bloqueadas na outbox. A credencial será provisionada na VM conforme [implantação](docs/deployment.md#gmail-e-credenciais-systemd).

## Operação

```sh
sar monthly --link-ids '[1,2]' --incluir-fatura --as-user admin
sar monthly --grupo-id 1 --incluir-fatura --data-inicio 2024-02-01 --data-fim 2024-02-29 --as-user admin
sar monthly --as-user admin
sar diagnostics --as-user admin
sar outbox-list --as-user admin
```

`monthly` envia sempre a fatura e o relatório juntos, em uma mensagem por instituição/grupo, para `svc.popce@rnp.br`. O assunto tem o formato `[SAR] - Fatura e Relatório Consolidado — Nome da instituição/grupo`; o corpo saúda a equipe e informa o período do relatório e o vencimento da fatura. A flag `--incluir-fatura` é mantida por compatibilidade, mas já é o padrão obrigatório. Sem seleção, processa instituições com perfil comercial. Execute via systemd para receber a credencial, conforme [implantação](docs/deployment.md).

`submitted` com `smtp_accepted_at` significa **aceito pelo Gmail via SMTP**, sem confirmar recebimento ou encaminhamento. Após registrar o resultado local, o SAR encerra. O processamento posterior pertence à aplicação low-code. A outbox aparece em Automação → Diagnóstico e no comando `outbox-list`.

Antes de emitir ou agendar uma fatura, configure em **Faturas → Sequências** o número inicial de cada instituição/grupo. Templates são compostos na ordem padrão, grupos ancestrais e instituição. Emissões manuais e automáticas compartilham a mesma série e aparecem no livro de emissões.

Agendamentos são gravados pela UI e reconciliados pelo serviço Linux. `run-schedule --id N` é a entrada do worker, não recebe texto de fatura no shell. A sincronização usa `sync-cron --launcher /usr/local/libexec/sar-run-schedule` sob o usuário dedicado `sar-cron`.

## Testes e documentação

```sh
python -m pytest -q
python -m ruff check src tests tools
python -m bandit -r src -ll
python -m pip_audit -r requirements.lock
python tools/security_scan.py
```

Os testes usam dados sintéticos e serviços falsos; não enviam e-mails nem alteram cron. A caracterização de PDFs compara texto e pixels contra snapshots dos renderizadores antigos sob as mesmas dependências. `tools/render_qa.py` gera PDFs e páginas PNG sintéticas em `tmp/pdfs`. PyMuPDF está limitado às ferramentas de teste/QA, não é dependência do serviço.

- [Contrato de comportamento](docs/behavior-contract.md)
- [Segurança e limites](docs/security-design.md)
- [Migração e retorno](docs/migration-runbook.md)
- [Implantação Linux](docs/deployment.md)
- [Pontos de extensão](docs/extensions.md)
- [Validação local](docs/validation.md)

Os recursos e SQL versionados estão dentro de `src/sar/resources` e `src/sar/migrations` para serem incluídos no pacote instalado. As pastas de orientação na raiz apenas apontam para essas fontes únicas.
