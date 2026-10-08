# Implantação Linux

## Pré-requisitos e limites

Servidor Linux com Python 3.12, systemd >=249, cron e sudo. Configure o fuso do sistema como `America/Fortaleza`; a reconciliação verifica `/etc/localtime` antes de alterar cron. SMTP Gmail, CA e token/conta Zabbix precisam ser configurados no servidor. Não há tentativa de provisionar esses serviços a partir desta estação Windows.

O ambiente local usa uma venv independente. A receita abaixo é para instalação no servidor, não foi executada aqui. Não copie `.venv` do Windows para Linux.

## Contas, diretórios e pacote

- Código `/opt/sar`, pertencente a root, sem escrita para contas de serviço.
- Conta `sar`, grupo `sar`: UI e workers; conta `sar-cron`, grupo primário `sar`: reconciliador.
- Diretório `/var/lib/sar`, proprietário `sar:sar`, modo `2770` (setgid para manter grupo). Banco modo `0660`; grupo composto somente por essas contas técnicas.
- Artifacts e locks de workers pertencem a `sar`, modo `0700`. `scheduler-locks` pertence a `sar-cron`, modo `0700`. Não misturar dados de outros sistemas.
- `/etc/sar/sar.env`: somente configuração não secreta; root:sar e modo `0640`.
- Em systemd 249 (Ubuntu 22 padrão), credenciais em `/etc/sar/credentials`, diretório root:root `0700`, arquivos `0600`, com `LoadCredential`. Em systemd >=250, Gmail cifrado em `/etc/credstore.encrypted`, usando `LoadCredentialEncrypted`. Nunca colocar a senha em linha de comando, histórico ou `.env`.

Criar venv Linux e instalar `requirements.lock`. Instalar o pacote previamente construído ou usar ferramentas de build fixadas e `pip install --no-deps --no-build-isolation .`. `src/sar/resources` e `src/sar/migrations` são package data. O executável `sar` será criado na venv.

Executar `sar migrate` como `sar` para banco novo **ou** `import-legacy` para destino inexistente. Não iniciar Streamlit antes da migração. Validar acesso de `sar-cron` ao banco e diretório de dados após importação.

## Unidades e cron

Instalar as unidades de `deploy/systemd` em `/etc/systemd/system`. Ajustar caminhos somente nos arquivos administrados por root. Para Zabbix com usuário/senha em vez de token, substituir a linha de token por duas linhas `LoadCredential` com nomes `zabbix-user` e `zabbix-password`.

O reconciliador usa seu próprio crontab (`sar-cron`). A conta `sar` não deve constar de `/etc/cron.allow`; adicionar apenas `sar-cron` e contas administrativas já autorizadas, preservando o conteúdo corporativo existente. O reconciliador precisa do mecanismo setgid/setuid normal do binário `crontab`; por isso sua unidade não usa `NoNewPrivileges=true`. A UI e o worker usam esse bloqueio.

Instalar `sar-run-schedule` e `sar-start-schedule` em `/usr/local/libexec`, root:root, modo `0755`. O launcher chama o helper por sudo; o helper aceita exatamente um ID numérico de até 10 dígitos e inicia exclusivamente `sar-worker@ID.service`. Instalar a regra de `sudoers-sar` somente depois de validar com `visudo -cf`.

Não conceder sudo genérico, shell root ou permissão de editar helpers a `sar-cron`. O helper é a única pequena operação privilegiada; o processamento Python permanece como `sar`.

Ativar `sar-ui.service` e `sar-scheduler.timer` após configurar dependências. Unidades `sar-worker@` são iniciadas pelo cron; não precisam ser habilitadas. Workers concorrentes aguardam o mesmo lock de arquivo. Uma unidade terminada inesperadamente deixa registros para recuperação/reconciliação, sem reenvio automático.

As linhas usam o marcador exclusivo `SAR-REFACTORED`; entradas do legado não são apagadas pelo reconciliador. Desativar o conjunto antigo explicitamente no corte para evitar duplo envio. Entradas de outros sistemas são preservadas. Como crontab não oferece compare-and-swap, não editar manualmente o crontab dedicado enquanto o reconciliador estiver ativo.

## Rede e notificações

Streamlit escuta somente `127.0.0.1`. Ajustar o exemplo Nginx com certificado e subnet VPN da equipe; o exemplo bloqueia clientes remotos por padrão. Firewall deve bloquear acesso direto à porta 8501 e limitar saída a Zabbix/Gmail SMTP e serviços necessários. Não reutilizar certificados de usuário ou desativar verificações TLS.

Gmail exige saída TCP 587 para `smtp.gmail.com` e uma cadeia CA válida. A rota é fixa: `svc.popce@gmail.com` → `svc.popce@rnp.br`. Todos os envios usam essa rota; endereços de contato e e-mails dos usuários não mudam o destinatário. Dois PDFs são obrigatórios; se a mensagem MIME exceder o SIZE anunciado pelo SMTP, o envio fica bloqueado sem dividir anexos.

## Observabilidade e critérios de ativação

Monitorar `journalctl -u sar-ui`, unidades `sar-worker@*`, estado do timer e `sar diagnostics`. Alertar para revisão pendente de sincronização, execuções failed/interrupted/partial, outbox blocked/indeterminate, disco cheio e expiração de certificado.

Antes de liberar: testes no Linux, `systemd-analyze verify` das unidades, validação de sudoers/Nginx, TLS real, conta Zabbix somente leitura, envio autorizado para `svc.popce@rnp.br` e restauração de backup. As verificações de systemd/cron e a entrega real não podem ser substituídas pelos testes simulados no Windows.

Usar volume cifrado e backup cifrado corporativos. Retenção de relatórios não é alterada automaticamente pelo SAR.

## Gmail e credenciais systemd

Estas instruções são para a implantação futura na VM. Nenhum segredo ou envio real foi criado no Windows.

1. Ative a verificação em duas etapas da conta `svc.popce@gmail.com` e gere uma senha de aplicativo exclusiva para o SAR. Não use a senha principal. [Google: senhas de aplicativo](https://support.google.com/mail/answer/185833?hl=pt-BR).
2. Confira `systemctl --version`. Ubuntu 22 normalmente usa systemd 249: `LoadCredentialEncrypted` exige >=250. [systemd: credenciais](https://systemd.io/CREDENTIALS/).
3. Instale o helper `deploy/provision-gmail-credential.py` como root, fora de diretório gravável por usuários. Execute `sudo python3 /opt/sar/deploy/provision-gmail-credential.py` em terminal interativo. O prompt é oculto; a senha nunca entra nos argumentos, ambiente ou logs. O helper usa cifragem em >=250 quando `systemd-creds` está disponível; caso contrário, instala arquivo protegido por root e informa a diretiva correspondente.
4. Em 249, a unidade `sar-worker@.service` fornecida usa `LoadCredential=gmail-app-password:/etc/sar/credentials/gmail-app-password`. O arquivo é texto protegido por permissões, **não cifrado em repouso**; proteja o volume/backups. A credencial Zabbix também usa `LoadCredential` nos exemplos compatíveis com 249.
5. Em >=250, instale `deploy/systemd/gmail-encrypted-worker.conf.example` como `/etc/systemd/system/sar-worker@.service.d/gmail.conf`. Preserve os nomes/fontes Zabbix já provisionados ao adaptar o drop-in. O nome lógico permanece `gmail-app-password` nos dois modos. A UI não precisa receber a senha Gmail.
6. Atualize `/etc/sar/sar.env` a partir de `.env.example`, removendo valores antigos de Outlook/relay. `SAR_MAIL_REPLY_TO` e `SAR_MAIL_CC` antigos são ignorados. Nenhuma senha SMTP é lida do ambiente.
7. Após backup do SQLite e dos artifacts, instale o pacote, pare UI/worker durante a migração, execute `sar migrate` como conta de serviço e valide versão 3. Não substitua o banco por um vazio. Rode `systemd-analyze verify` e `systemctl daemon-reload`, depois inicie a UI e agendamentos novos.

### Execução manual com a mesma credencial

`monthly` e `dispatch-pending` precisam executar em unidade systemd com a credencial. Exemplo para systemd 249, substituindo os IDs/usuário conforme cadastro local:

```sh
sudo systemd-run --wait --collect --unit=sar-monthly-manual \
  --property=User=sar --property=Group=sar --property=WorkingDirectory=/opt/sar \
  --property=EnvironmentFile=/etc/sar/sar.env --property=UMask=0077 \
  --property=LoadCredential=zabbix-token:/etc/sar/credentials/zabbix-token \
  --property=LoadCredential=gmail-app-password:/etc/sar/credentials/gmail-app-password \
  /opt/sar/.venv/bin/sar monthly --link-ids '[1]' --as-user admin
```

Em >=250 troque somente a propriedade Gmail por `LoadCredentialEncrypted=gmail-app-password:/etc/credstore.encrypted/sar-gmail-app-password`. Caso Zabbix use usuário/senha, forneça as duas credenciais correspondentes. Não exporte `CREDENTIALS_DIRECTORY` manualmente nem leia o segredo para uma variável de shell.

### Validação, recuperação e rotação

Crie primeiro agendamentos novos com sequência de fatura configurada. Agendamentos antigos sem fatura e mensagens legadas pendentes são recusados e devem ser recriados; registros e PDFs existentes são preservados.

Faça um envio autorizado para `svc.popce@rnp.br` com dois PDFs de teste, conferindo assunto, competência e vencimento. O critério do SAR é `submitted` com `smtp_accepted_at` em UTC na outbox e diagnóstico. Não há callback, consulta à caixa, armazenamento remoto ou confirmação low-code no SAR.

Rejeição SMTP explícita/falha de TLS/autenticação gera `blocked`; queda de conexão durante submissão gera `indeterminate`. Não há reenvio automático. Reconcilie pelo Message-ID estável antes de autorizar nova tentativa. Marcar uma submissão manualmente não fabrica data de aceitação SMTP. Se o banco falhar após DATA aceito, preserve `sending` para recuperação como `indeterminate`.

Para rotacionar, revogue a senha de aplicativo antiga no Google e execute novamente o helper em terminal oculto; novas execuções systemd carregam a nova credencial. Mudança da senha principal pode revogar senhas de aplicativo. Nunca exiba conteúdo de credenciais em diagnóstico/journal.
