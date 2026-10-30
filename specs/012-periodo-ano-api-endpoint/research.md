# Research — 012 Período "Desde o começo do ano", API por consentimento e visão por endpoint

Todas as medições abaixo foram feitas na base de 2026-10-29 (`data-loader/data/consents.db`, dados até 2026-09-25). Nenhum item ficou como "NEEDS CLARIFICATION".

## Decisão 1 — "Desde o começo do ano" é só frontend

- **Decisão**: acrescentar o período `ytd` ao frontend. A data inicial é 1º de janeiro do ano de `V2.meta.data_through`; o backend não muda.
- **Racional**: os três endpoints que recebem período (`/ranking`, `/evolution`, `/institution/{uuid}`) já aceitam `start` livre e resolvem a primeira observação com `M._period_start`, que devolve a primeira semana a partir de `start`. Para 2026 isso dá a sexta-feira de 02/01/2026. O ano vem do dado, não do relógio (spec, Edge Cases).
- **Alternativas**: parâmetro `period=ytd` no backend (rejeitado: duplicaria a regra de datas e mudaria três contratos sem ganho).

## Decisão 2 — Lista de períodos e `periodStart` passam para `shell.js`

- **Decisão**: criar `V2.PERIODS` e `V2.periodStart(period)` em `shell.js` e remover as cópias de `index.html`, `evolucao.html` e `instituicao.html`.
- **Racional**: as três páginas têm hoje o mesmo `PERIODS` e o mesmo cálculo de data inicial. Acrescentar uma quarta opção em três lugares é o tipo de duplicação com risco de divergência que o Princípio I proíbe; são exatamente 3 usos reais. A Constituição (§6.8) já manda o código compartilhado ir para `shell.js`.
- **Efeito colateral aceito**: sessões antigas com `period` salvo continuam válidas (a lista é um superconjunto) e valores desconhecidos já caem em `12m`.
- **Alternativas**: acrescentar a opção em cada página (rejeitado: três cópias).

## Decisão 3 — O ritmo trimestral não depende do período

- **Decisão**: nenhum tratamento especial no `ytd` para o ritmo trimestral.
- **Racional**: `quarterly_pace` é calculado sobre `full_monthly` (histórico inteiro até a semana final), então um período curto não o quebra. O que depende do período é o crescimento, os ganhos e perdas de participação e as linhas. Para esses, o aviso de FR-005 aparece quando o período tem menos de 3 pontos.

## Decisão 4 — Escala por consentimento via parâmetro `scale`

- **Decisão**: `/api/v2/evolution` ganha `scale` ∈ {`total`, `per_consent`}, padrão `total` no contrato, válido só com `metric=api` (422 caso contrário). O padrão `per_consent` da tela é do frontend (Clarifications), não da API.
- **Racional**: é o mesmo nome e a mesma validação de `/api/v2/ranking` (`_SCALES`, 422 fora de `metric=api`). Manter o padrão da API em `total` não quebra nenhum chamador atual (SC-005); o frontend manda `scale=per_consent` por padrão.
- **Alternativas**: nova métrica `api_per_consent` como na aba da instituição (rejeitado: `/evolution` e `/ranking` já se alinham por `scale`; duas formas de pedir a mesma coisa).

## Decisão 5 — Série por consentimento sem tabela nova

- **Decisão**: calcular a série com as funções existentes, em memória: para cada instituição, `M.per_consent_30d(chamadas semanais, únicos PF + PJ semanais)`; para o ecossistema, `M.paired_sums` e depois `per_consent_30d`.
- **Racional**: é a regra única do painel (spec, FR-007): 4 semanas normalizadas para 30 dias ÷ média de únicos das mesmas 4 semanas, e o ecossistema só conta instituições com chamadas na semana. Como o `/ranking` e a aba da instituição usam as mesmas funções, SC-002 (diferença zero) vale por construção.
- **Crescimento**: sobre a série por consentimento, já suavizada por 4 semanas, com `growth_stock` (valor do início contra o do fim do período), e não `growth_flow`, que compara médias de fluxo. Instituição que estreou no período mostra "estreou mmm/aa" pela mesma `format_growth`.
- **Dados de entrada**: `M.load_metric("api")` (de `api_status_weekly`, status 200) e `M.load_metric("unique_total")` (PF + PJ), ambos já em cache.

## Decisão 6 — Resposta quando a participação não se aplica

- **Decisão**: com `scale=per_consent`, a resposta mantém o mesmo formato e marca o que não se aplica: `share_available: false`, `series[].shares = null`, `group_share = []`, `group_share_change = []`, `share_changes = []`, `headline.top_gainer = headline.top_loser = null`. Os campos `headline.ecosystem_growth`, `series[].values/last/growth`, `quarterly_pace` e `ecosystem_quarterly_pace` passam a ser sobre o valor por consentimento.
- **Racional**: mudança aditiva (campos novos, nenhum removido), então os clientes atuais continuam funcionando. A tela decide o que desativar a partir de `share_available`, e a explicação ("participação não se aplica a chamadas por consentimento") fica no frontend.

## Decisão 7 — Fonte do detalhe por endpoint: tabela pré-agregada nova

- **Decisão**: criar `api_endpoint_weekly(date, receptor_uuid, receptor, api, endpoint_id, endpoint, total)`, preenchida por `scrapers.refresh_api_endpoint_weekly`.
- **Racional**: `api_requests` tem 5.930.804 linhas (1.320.911 agregadas e 4.609.893 por endpoint, as duas em todas as 143 datas). Agrupar por data × receptor × API × endpoint, sem transmissor e sem status, deu 196.412 linhas em 7,1 s, o que é inviável no caminho quente e é exatamente o caso que o Princípio IV manda pré-agregar. Estender `api_group_weekly` (PK `date, receptor_uuid, grp`) mudaria a granularidade de uma tabela que o legado lê.
- **Alternativas**: consultar `api_requests` ao vivo (rejeitado: 7 s); embutir no `api_group_weekly` (rejeitado: quebra o legado); calcular no startup do dashboard (rejeitado: o dashboard só lê, e o custo repetiria a cada instância).

## Decisão 8 — Base de sucesso (status 200)

- **Decisão**: `api_endpoint_weekly` só soma `status = 200` e exclui `api = 'consents'`.
- **Racional**: a visão por grupo que o endpoint substitui parcialmente lê `api_group_weekly`, que também filtra `status = 200` e exclui `consents`. Usar a mesma base é o que garante o SC-003 (soma dos endpoints = total da API na visão por grupo). Erros (500) já têm sua própria tabela e bloco ("taxa de erro").

## Decisão 9 — "Sem endpoint identificado" como linha `endpoint_id = 0`

- **Decisão**: no refresh, para cada (data, receptor, API), `não atribuído = MAX(0, soma do agregado − soma dos endpoints)`, gravada como linha com `endpoint_id = 0` e `endpoint = ''`. Se não existir linha agregada, a parcela é 0.
- **Evidência**: casando por data, receptor, transmissor, API e status (desde 2026-08-01, 59.855 comparações), o agregado é igual à soma dos endpoints em 59.591 (99,56%), maior em 264 (0,44%) e **menor em nenhuma**. Logo, o agregado nunca é inferior à soma, a parcela nunca fica negativa na prática, e o `MAX(0, …)` só protege contra dado futuro estranho.
- **Alternativas**: ignorar a diferença (rejeitado: SC-003 falharia em 0,44% dos casos sem explicação).

## Decisão 10 — Catálogo para os endpoints com valor zero

- **Decisão**: o catálogo vem de `endpoint_history` (`api`, `endpoint_id`, `endpoint_label`), unido aos endpoints vistos em `api_endpoint_weekly`. O rótulo é o mais recente do catálogo.
- **Evidência**: o catálogo tem 18 APIs e 95 endpoints; os 74 endpoints usados em `api_requests` estão todos nele (0 faltando), 21 do catálogo nunca foram usados, e nenhum (API, endpoint) tem mais de um rótulo. A união com os endpoints vistos protege contra uma API nova que ainda não esteja no catálogo.
- **Efeito**: confirma a decisão de "todos os endpoints do catálogo, com zeros ao final" (Clarifications). Só as APIs de `API_GROUPS` (menos `Resource`) são oferecidas no seletor.

## Decisão 11 — Endpoint separado, carregado sob demanda

- **Decisão**: novo `GET /api/v2/institution/{uuid}/endpoints?api=&compare=`, chamado só ao abrir "Por endpoint" ou ao trocar de API. `/api/v2/institution/{uuid}` não muda.
- **Racional**: preserva o contrato e os testes atuais (FR-019, SC-005), não aumenta a carga de quem nunca abre a visão por endpoint e permite um cache próprio. A lista de APIs do seletor e as linhas da API escolhida vêm na mesma resposta (um clique, uma chamada).
- **Alternativas**: embutir tudo em `/institution/{uuid}` (rejeitado: carga extra para todos e risco de regressão no contrato existente).

## Decisão 12 — Estado da tela

- **Decisão**: a escala de "Como evolui?" é persistida em `opf:v2:filters` (campo `evo_scale`), para sobreviver à troca de métrica e de aba (FR-011). A visão "Por endpoint" e a API escolhida **não** são persistidas: vivem na página e voltam ao padrão (por grupo) ao trocar de aba (spec, cenário 6 da História 3).
- **Racional**: segue §6.8 (a página só escreve os campos que possui e preserva os demais).

## Decisão 13 — Implantação da tabela nova

- **Decisão**: o `compute_signals.py` passa a chamar o refresh novo, o que preenche a base já existente sem recoletar; a coleta completa também o chama no fim, ao lado de `refresh_api_group_weekly` e `refresh_api_status_weekly`.
- **Racional**: igual ao que já se faz com `api_status_weekly` (CLAUDE.md: "uma coleta interrompida deixa as tabelas semanais desatualizadas até rodar `compute_signals.py`"). O deploy do dashboard antes da base nova é seguro por causa da resposta `unavailable`.
