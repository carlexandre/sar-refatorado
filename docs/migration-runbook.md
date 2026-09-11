# Migração e retorno operacional

## Atualização para autenticação e faturas sequenciais

1. Parar UI, timer e workers e criar backup consistente do banco, `-wal`, `-shm` e artifacts.
2. Executar `sar migrate`; o migrador aplica scripts pendentes em ordem e valida chaves estrangeiras.
3. Definir `SAR_ACCESS_MODE=local` e executar `sar auth bootstrap-admin --username ... --display-name ... --claim-legacy-schedules`.
4. Conferir a reconciliação dos artifacts de fatura antigos. Números não são inferidos de filenames.
5. Configurar template e próximo número oficial de cada alvo antes de reativar agendamentos com fatura.
6. Validar login, prévia, emissão controlada e diagnósticos antes de iniciar timer/workers.

## Ensaio

1. Obter cópia consistente do SQLite legado e inventário de PDFs. Não importar módulos legados: `database.py` alterava esquema no import.
2. Definir diretório de dados novo. `import-legacy` recusa banco de destino já existente e nunca atualiza o banco de origem.
3. Executar `sar import-legacy --source ... --source-artifacts ...`.
4. Conferir o resumo por tabela: origem = importados + reconciliação. Verificar SHA dos arquivos e `PRAGMA foreign_key_check`.
5. Rever a tabela `reconciliation` em ambiente administrativo restrito. Registros sem instituição não criam clientes fictícios; ficam preservados como JSON com origem e motivo. Referências de arquivo inválidas preservam histórico com indicador de indisponibilidade.
6. Todos os PDFs válidos dentro da raiz autorizada são copiados, inclusive arquivos sem histórico válido. Esses arquivos recebem escopo desconhecido e não são acessíveis por usuários de escopo parcial.
7. Não há resolução automática de conflitos comerciais ou de identidade. Corrigir vínculos somente com evidência administrativa; preservar o registro original de reconciliação.

Se a importação falhar, ela reverte a transação e remove os artifacts que acabou de criar. O banco inicializado vazio permanece para diagnóstico. Escolher novo diretório de ensaio após investigar; não repetir sobre dados existentes.

O script `tools/verify_local_migration.py` fez o ensaio desta cópia em diretório temporário, verificou hashes e removeu apenas sua própria cópia temporária. O resultado agregado está em `migration-verification.json`; não contém nomes de clientes ou credenciais.

## Corte

1. Suspender agendamentos SAR antigos e alterações cadastrais na janela de manutenção.
2. Fazer backup consistente com a API de backup SQLite, ou parar todos os processos antes de copiar banco/WAL. Copiar PDFs e registrar hashes. Copiar apenas o arquivo `.db` em uso pode perder transações do WAL.
3. Migrar para destino exclusivo e validar contagens, documentos, perfis, períodos e agendamentos.
4. Instalar/validar serviços conforme `deployment.md`. O marcador novo não remove as entradas antigas: verificar explicitamente que não existem dois conjuntos ativos.
5. Fazer geração e envio de homologação para destinatário autorizado; habilitar o novo agendador e acompanhar a primeira ocorrência.

## Mensagens e falhas

`submitted` significa aceitação pelo relay, não entrega final. `blocked` indica que não houve envio confirmado por configuração/autorização ou falha anterior à submissão. `indeterminate` exige consulta dos logs do relay pelo Message-ID; `interrupted` identifica processo terminado antes do encerramento.

```sh
sar outbox-list
sar reconcile-message --id ID --decision submitted --reason CHAMADO-123
# OU: confirmar que não houve entrega e liberar nova tentativa
sar reconcile-message --id ID --decision retry --reason CHAMADO-123
sar dispatch-pending --execution-id EXECUCAO
# OU: cancelar uma mensagem sem enviar
sar reconcile-message --id ID --decision cancelled --reason CHAMADO-123
```

`reconcile-message` não envia. `dispatch-pending` envia somente pendências da execução indicada, sob lock e com revalidação de permissões. Não inserir segredos em `--reason`. Não reenviar toda a competência para corrigir apenas uma mensagem sem antes conferir a outbox.

O resultado original da execução permanece como histórico da ocorrência; a outbox e auditoria registram a resolução posterior. Não prometer processamento exatamente uma vez no transporte SMTP.

## Retorno

Parar timer e workers novos. Preservar banco, PDFs, auditoria e outbox novos antes de qualquer restauração. Conciliar mensagens já submetidas e alterações cadastrais ocorridas após o corte. Só reativar o conjunto antigo após excluir risco de duplo envio. Rollback de arquivos não desfaz e-mails nem desfaz automaticamente mudanças de dados.
