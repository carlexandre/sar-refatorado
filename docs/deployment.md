# Implantação Linux

## Pré-requisitos e limites

Servidor Linux com Python 3.12, systemd com `LoadCredentialEncrypted`, cron e sudo. Configure o fuso do sistema como `America/Fortaleza`; a reconciliação verifica `/etc/localtime` antes de alterar cron. SMTP Relay, CA e token/conta Zabbix são provisionados pela infraestrutura. Não há tentativa de provisionar esses serviços a partir desta estação Windows.

O ambiente local usa uma venv independente. A receita abaixo é para instalação no servidor, não foi executada aqui. Não copie `.venv` do Windows para Linux.

## Contas, diretórios e pacote

- Código `/opt/sar`, pertencente a root, sem escrita para contas de serviço.
- Conta `sar`, grupo `sar`: UI e workers; conta `sar-cron`, grupo primário `sar`: reconciliador.
- Diretório `/var/lib/sar`, proprietário `sar:sar`, modo `2770` (setgid para manter grupo). Banco modo `0660`; grupo composto somente por essas contas técnicas.
- Artifacts e locks de workers pertencem a `sar`, modo `0700`. `scheduler-locks` pertence a `sar-cron`, modo `0700`. Não misturar dados de outros sistemas.
- `/etc/sar/sar.env`: somente configuração não secreta; root:sar e modo `0640`.
- Credenciais cifradas em `/etc/credstore.encrypted`, root:root. Usar `systemd-creds encrypt` conforme política corporativa e fornecer o conteúdo via canal seguro, nunca em linha de comando, histórico de shell ou `.env`.

Criar venv Linux e instalar `requirements.lock`. Instalar o pacote previamente construído ou usar ferramentas de build fixadas e `pip install --no-deps --no-build-isolation .`. `src/sar/resources` e `src/sar/migrations` são package data. O executável `sar` será criado na venv.

Executar `sar migrate` como `sar` para banco novo **ou** `import-legacy` para destino inexistente. Não iniciar Streamlit antes da migração. Validar acesso de `sar-cron` ao banco e diretório de dados após importação.

## Unidades e cron

Instalar as unidades de `deploy/systemd` em `/etc/systemd/system`. Ajustar caminhos somente nos arquivos administrados por root. Para Zabbix com usuário/senha em vez de token, substituir a linha de token por duas linhas `LoadCredentialEncrypted` com nomes `zabbix-user` e `zabbix-password`.

O reconciliador usa seu próprio crontab (`sar-cron`). A conta `sar` não deve constar de `/etc/cron.allow`; adicionar apenas `sar-cron` e contas administrativas já autorizadas, preservando o conteúdo corporativo existente. O reconciliador precisa do mecanismo setgid/setuid normal do binário `crontab`; por isso sua unidade não usa `NoNewPrivileges=true`. A UI e o worker usam esse bloqueio.

Instalar `sar-run-schedule` e `sar-start-schedule` em `/usr/local/libexec`, root:root, modo `0755`. O launcher chama o helper por sudo; o helper aceita exatamente um ID numérico de até 10 dígitos e inicia exclusivamente `sar-worker@ID.service`. Instalar a regra de `sudoers-sar` somente depois de validar com `visudo -cf`.

Não conceder sudo genérico, shell root ou permissão de editar helpers a `sar-cron`. O helper é a única pequena operação privilegiada; o processamento Python permanece como `sar`.

Ativar `sar-ui.service` e `sar-scheduler.timer` após configurar dependências. Unidades `sar-worker@` são iniciadas pelo cron; não precisam ser habilitadas. Workers concorrentes aguardam o mesmo lock de arquivo. Uma unidade terminada inesperadamente deixa registros para recuperação/reconciliação, sem reenvio automático.

As linhas usam o marcador exclusivo `SAR-REFACTORED`; entradas do legado não são apagadas pelo reconciliador. Desativar o conjunto antigo explicitamente no corte para evitar duplo envio. Entradas de outros sistemas são preservadas. Como crontab não oferece compare-and-swap, não editar manualmente o crontab dedicado enquanto o reconciliador estiver ativo.

## Rede e notificações

Streamlit escuta somente `127.0.0.1`. Ajustar o exemplo Nginx com certificado e subnet VPN da equipe; o exemplo bloqueia clientes remotos por padrão. Firewall deve bloquear acesso direto à porta 8501 e limitar saída a Zabbix/relay e serviços necessários. Não reutilizar certificados de usuário ou desativar verificações TLS.

Configurar relay autorizado para o endereço fixo `SAR_MAIL_FROM`, caixa de resposta `SAR_MAIL_REPLY_TO` e grupo `SAR_MAIL_CC`. Validar remetente de envelope, domínio, limites de anexos, SPF/DKIM/DMARC e entregabilidade com uma instituição de teste autorizada.

## Observabilidade e critérios de ativação

Monitorar `journalctl -u sar-ui`, unidades `sar-worker@*`, estado do timer e `sar diagnostics`. Alertar para revisão pendente de sincronização, execuções failed/interrupted/partial, outbox blocked/indeterminate, disco cheio e expiração de certificado.

Antes de liberar: testes no Linux, `systemd-analyze verify` das unidades, validação de sudoers/Nginx, TLS real, conta Zabbix somente leitura, envio para caixa de homologação e restauração de backup. As verificações de systemd/cron e a entrega real não podem ser substituídas pelos testes simulados no Windows.

Usar volume cifrado e backup cifrado corporativos. Retenção de relatórios não é alterada automaticamente pelo SAR.
