# Contrato de comportamento

## Regras preservadas

| Área | Regra |
|---|---|
| Navegação | Home, Gerar, Faturas, Cadastros, Historico, Automacao, inclusive parâmetro `page`. |
| Relatório manual | Uma a três instituições selecionadas; consolidado; datas padrão hoje-30 dias e hoje. |
| Extração | `history=3`; trends quando vazio ou primeiro registro mais de 86400 segundos após o início. |
| Intervalo | Preserva `Timestamp` ingênuo tratado como UTC, limite superior meia-noite final +86400 segundos. Não foi aplicada mudança silenciosa para horário local. |
| Estatísticas | History: máximo/média de value. Trends: máximo de value_max e média aritmética de value_avg. Mbps = valor/1.000.000. |
| Gráfico | Trends usa value_max; outer join por clock; forward fill; zero inicial; estilo e escalas legados. |
| Alertas | Termos bandwidth, uptime, restart; recuperação consultada separadamente; America/Fortaleza para apresentação. |
| Utilização | Alta em >=75%, crítica em >=90%; capacidade desconhecida mantém fallback de 1000 Mbps. |
| Faturas | Float e formatação em duas casas preservados; itens vazios produzem conectividade com valor zero. |
| Grupo | Inclui descendentes recursivos no relatório; itens de fatura são exclusivos do grupo. |
| Cadastros | Nome sugerido remove sufixos de rede e prefixo RG; host da instituição permanece fixo na edição. |
| Perfil em lote | Dados comerciais e itens substituem os dados das instituições selecionadas, em uma transação. |
| Automação UI | Instituição exige e-mail e perfil; grupo exige e-mail e ao menos uma instituição; sobreposição de instituições em agendamentos ativos conflita mesmo em horários distintos. |
| CLI | Seleção individual permite instituição sem perfil; modo global exige perfil; grupo utiliza seu contato; sem dados não envia. |
| Falha de fatura | Relatório pode ser enviado sozinho, como no legado, com resultado parcial explícito. Textos legados são preservados. |
| Histórico | Filtros por instituição/grupo/data; três meses = 90 dias; lista de download limitada a 15 registros. |

## Correções explícitas

- Sem fallback TLS inseguro e sem credenciais em `.env`.
- E-mail com remetente fixo, Reply-To validado e CC GigaFOR.
- Texto cadastrado não é HTML executável. Busca por nome usa texto literal, evitando interpretação de regex fornecida pelo usuário.
- Sem SQL na UI, envio SMTP na UI ou escrita de cron no processo web.
- Datas inválidas, referências inexistentes e JSON malformado recebem erro claro.
- PDFs não se sobrescrevem; identificador interno não é nome de instituição.
- Histórico só registra instituições efetivamente incluídas.
- Exclusões com dependências e reativação de agendamentos conflitantes são bloqueadas.
- Pausa permanece disponível mesmo quando o destinatário deixou de ser elegível.
- Diagnóstico usa auditoria estruturada; não permite apagar o registro de auditoria nem expor crontab/logs brutos.
- Resultado SMTP indeterminado exige reconciliação; não há promessa de entrega exatamente uma vez.

## Apresentação

Documentos conservam o layout legado, incluindo paginação e substituição de caracteres por Latin-1. A comparação visual não ignora diferenças de conteúdo. A UI mantém as funções e rotas, usando componentes nativos seguros; o editor de itens é uma tabela editável com inclusão/remoção de linhas. O hack JavaScript de tema/navegação e a dependência CDN foram removidos. Não se afirma identidade pixel a pixel da interface web.

Uma mudança para Decimal, ajuste de fuso na consulta ao Zabbix, alteração de regras de alerta ou novo layout de documento requer atualização deste contrato e dos testes de caracterização.
