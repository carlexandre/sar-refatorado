# Validação da implementação

Validação local em 11/09/2026, Windows, Python 3.12.14, ambiente virtual exclusivo da nova pasta.

## Resultados

- **78 testes passaram**: domínio, serviços, migrações v1→v2, autenticação local, sessão e tema preservados na navegação, RBAC/escopos, herança de templates, numeração concorrente e idempotente, recuperação de outbox, interfaces de identidade e telas Streamlit. Inclui regressões de tema claro, controles atuais do Streamlit, layout dos cards, bloqueio de acesso direto e de download fora do escopo.
- **Ruff:** sem achados.
- **Bandit:** sem achados de severidade média ou alta no código de produção. SQL foi convertido para consultas literais/whitelist; não foram adicionadas supressões globais.
- **Guardrails de código:** nenhum segredo literal, shell inseguro, HTML arbitrário ou desativação TLS identificado pelos padrões verificados.
- **pip-audit:** nenhuma vulnerabilidade conhecida encontrada nas dependências de produção fixadas; relatório em `dependency-audit.json`. Resultado válido para a consulta realizada, não garantia de ausência de vulnerabilidades futuras.
- **PDFs:** comparação de texto e pixels de todas as páginas para relatórios de uma/três instituições e faturas com/sem itens. Processamento de métricas comparado contra função legada congelada. Relatório sintético com gráfico real e fatura foram renderizados; cinco páginas foram inspecionadas visualmente.
- **Empacotamento:** wheel `sar_reports-1.0.0-py3-none-any.whl` gerado, incluindo recursos e migração SQL.

Os avisos de depreciação FPDF vêm também dos snapshots legados usados na comparação; são esperados nessa caracterização. Dependências estão fixadas. A paginação/textos legados são preservados, inclusive a possibilidade de conclusão continuar em outra página.

## Ensaio de migração da cópia local

O ensaio usou banco de destino temporário e origem em modo somente leitura. O relatório agregado está em `migration-verification.json`.

| Conteúdo | Resultado |
|---|---|
| Grupos | 2 importados |
| Instituições | 1 importada |
| Perfis comerciais | 1 importado, 1 preservado em reconciliação |
| Histórico | 1 importado, 5 preservados em reconciliação |
| Agendamentos | 1 importado |
| PDFs | 2 preservados, com escopo desconhecido quando necessário |
| Referências inválidas no destino | 0 |
| Integridade da origem | Hashes de 12 arquivos conferidos sem alteração |

Nenhum e-mail foi enviado, credencial real testada ou crontab alterado. A cópia de ensaio foi removida ao terminar; a aplicação não foi apontada para os dados reais.

## Verificações necessárias no ambiente corporativo

Não executadas nesta estação: systemd/cron/sudoers/Nginx reais, conectividade Zabbix com CA corporativa, identidade de máquina no relay, entrega de e-mail, permissões POSIX efetivas entre contas de serviço, volume/backup cifrados e restauração operacional no servidor. As instruções e unidades estão entregues, mas sua ativação depende do provisionamento descrito em `deployment.md`.

Autenticação local, RBAC persistido, administração de usuários, editor de templates e livro sequencial de emissões estão implementados. LDAP permanece deliberadamente como contrato de extensão: não há conexão LDAP apresentada como funcional nesta entrega.
