# SAR — versão refatorada

Monólito modular Python: Streamlit apresenta as telas; os serviços executam as regras; adaptadores implementam SQLite, Zabbix, documentos, arquivos e SMTP Relay. Workers e CLI usam os mesmos serviços.

A versão original permanece separada. Nenhum módulo legado é importado pela aplicação nova. A aplicação oferece login local, RBAC, templates de fatura herdáveis e numeração transacional. O contrato de identidade está preparado para um adaptador LDAP posterior.

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
- `CREDENTIALS_DIRECTORY`: fornecido pelo systemd; contém `zabbix-token` ou `zabbix-user` e `zabbix-password`. Segredos não são copiados do `.env` legado.
- `SAR_SMTP_HOST`, `SAR_SMTP_PORT`, `SAR_SMTP_TLS=starttls|implicit`: relay corporativo com TLS obrigatório.
- `SAR_MAIL_FROM`, `SAR_MAIL_REPLY_TO`, `SAR_MAIL_CC`: remetente SAR, caixa institucional e grupo GigaFOR. São endereços de configuração, não senhas.
- `SAR_TIMEZONE=America/Fortaleza`: o fuso do servidor cron deve ser o mesmo.

Sem Zabbix configurado, consultas falham de forma segura; cadastros existentes e histórico continuam disponíveis. Sem relay configurado, documentos ainda podem ser gerados e as mensagens ficam bloqueadas na outbox. A entrega corporativa não está provisionada por este repositório.

## Operação

```sh
sar monthly --link-ids '[1,2]' --incluir-fatura --as-user admin
sar monthly --grupo-id 1 --incluir-fatura --data-inicio 2024-02-01 --data-fim 2024-02-29 --as-user admin
sar monthly --as-user admin
sar diagnostics --as-user admin
sar outbox-list --as-user admin
```

`monthly` envia e-mails se o relay estiver configurado. Sem seleção, processa instituições com perfil comercial, como a CLI anterior. Não use esses comandos como teste contra destinatários reais.

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
