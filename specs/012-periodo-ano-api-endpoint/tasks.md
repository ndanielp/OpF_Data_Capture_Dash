---
description: "Task list for 012-periodo-ano-api-endpoint"
---

# Tasks: Período "Desde o começo do ano", API por consentimento em "Como evolui?" e visão por endpoint

**Input**: Design documents from `/specs/012-periodo-ano-api-endpoint/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/v2-api-delta.md, quickstart.md

**Tests**: Incluídos. A Constituição (Princípio II) exige:
- teste de integração em SQLite real para toda escrita nova no banco;
- teste HTTP (caminho feliz + erro) para todo endpoint novo ou alterado;
- validação manual no navegador para toda mudança de tela.

**Organization**: As tarefas estão agrupadas por user story da spec:
- US1: Período "Desde o começo do ano" (P1) 🎯 MVP
- US2: Chamadas de API por consentimento em "Como evolui?" (P2)
- US3: Visão por endpoint em "Como opera uma instituição?" (P3)

Cada fase de história é um PR próprio contra `main` (plan.md, "Entrega por fases"). A fase 3 do plano (dados) e a 4 (tela) formam a US3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: US1–US3

## Path Conventions

- **Escrita no banco:** só `data-loader/`.
- **Leitura e telas:** `dashboard/`.
- **Regras numéricas e formato das respostas:** em `research.md`, `data-model.md` e `contracts/v2-api-delta.md`. Não reinventar nas tarefas.
- Comandos de teste: `cd dashboard && .venv/bin/python -m pytest …` e `cd data-loader && .venv/bin/python -m pytest …`.

---

## Phase 1: Setup

**Purpose**: Garantir a linha de base antes de mexer em qualquer arquivo.

- [ ] T001 Rodar as suítes atuais (`dashboard/tests` e `data-loader/tests`) na branch `012-periodo-ano-api-endpoint` e anotar quais testes passam. Qualquer falha anterior à feature deve ser registrada e não corrigida aqui (SC-005 compara contra essa linha de base). Nenhum arquivo é alterado.

---

## Phase 2: Foundational

Nenhuma tarefa bloqueante. As três histórias não compartilham pré-requisito: a US1 só mexe no frontend, a US2 só no `/evolution` e em `evolucao.html`, e a US3 cria a tabela e o endpoint novos. Podem começar logo após o T001; a ordem recomendada é P1 → P2 → P3 porque US1 e US2 editam o mesmo arquivo (`dashboard/gui/v2/evolucao.html`).

---

## Phase 3: User Story 1 - Ver o ano até agora (Priority: P1) 🎯 MVP

**Goal**: A opção "Desde o começo do ano" existe no filtro de período de todas as abas que o usam, vai de 1º de janeiro do ano da última semana com dados até essa semana e é mantida ao trocar de aba.

**Independent Test**: Com a base atual (dados até 25/09/2026), escolher "Desde o começo do ano" em "Como evolui?" e conferir que o início é a primeira semana de 2026, o fim é 25/09/2026 e os cartões dizem "desde o começo do ano"; trocar de aba e ver o período mantido; voltar aos períodos antigos e ver os mesmos números de antes.

### Tests for User Story 1

- [ ] T002 [P] [US1] Em `dashboard/tests/test_v2_evolution.py`, adicionar teste HTTP de `GET /api/v2/evolution?metric=unique_pf&start=<1º de janeiro do ano da base sintética>`: `headline.ecosystem_growth.from` deve ser o valor do ecossistema na primeira semana com data maior ou igual a `start` (regra `M._period_start`), `period.start` deve ecoar o `start` enviado e o status deve ser 200. Incluir um segundo caso com `start` igual à penúltima semana (período de 1 ponto): 200 e crescimento "sem base", sem erro (FR-005).

### Implementation for User Story 1

- [ ] T003 [US1] Em `dashboard/gui/v2/shell.js`, criar `V2.PERIODS` (mesmas tuplas `[rótulo, dias, rótulo curto]` de hoje: `12m`, `6m`, `3m`, `all`) com a opção nova `ytd: ['Desde o começo do ano', 'ytd', 'no ano']` entre `3m` e `all`, e `V2.periodStart(period)`: `all` → `2000-01-01`, `ytd` → `AAAA-01-01` com AAAA = ano de `V2.meta.data_through`, demais → `data_through` menos os dias. Ajuda de comentário só para o porquê (o ano vem do dado, não do relógio).
- [ ] T004 [P] [US1] Em `dashboard/gui/v2/index.html`, remover o `PERIODS` e o `periodStart()` locais (linhas ~28 e ~50) e usar `V2.PERIODS` / `V2.periodStart`; manter a validação do período salvo (valor desconhecido cai em `12m`) e conferir os textos que usam `PERIODS[st.period][2]` (cartões, cabeçalho de crescimento, CSV) para a opção `ytd`.
- [ ] T005 [P] [US1] Em `dashboard/gui/v2/evolucao.html`, remover o `PERIODS` (linha ~57) e o `periodStart()` (linha ~91) locais e usar `V2.PERIODS` / `V2.periodStart`; ajustar os textos condicionados a `st.period === 'all'` (por exemplo "desde o início", linha ~373) para também tratar `ytd` ("desde o começo do ano").
- [ ] T006 [P] [US1] Em `dashboard/gui/v2/instituicao.html`, remover o `PERIODS` (linha ~62) e o `periodStart()` (linha ~81) locais e usar `V2.PERIODS` / `V2.periodStart`; conferir o texto de crescimento (linha ~178) para `ytd`.
- [ ] T007 [US1] Em `dashboard/gui/v2/evolucao.html`, exibir o aviso "Poucos dados neste período" no card do gráfico de linhas quando `d.points.length < 3` (FR-005), sem esconder o que existe. Depende de T005.
- [ ] T008 [US1] Validar no navegador (porta 8000) o roteiro "Período 'Desde o começo do ano'" de `quickstart.md`, nas três abas com período, e conferir que `12m`, `6m`, `3m` e `all` mostram os mesmos números de antes (SC-005).

**Checkpoint**: US1 entregue e testável sozinha. É o MVP e pode ir para produção sem tocar no banco.

---

## Phase 4: User Story 2 - Chamadas de API por consentimento em "Como evolui?" (Priority: P2)

**Goal**: Na métrica "Chamadas de API" de "Como evolui?", a escala "por consentimento/mês" é a padrão, com o volume a um clique; os blocos de participação ficam desativados nessa escala, com explicação.

**Independent Test**: Para uma instituição e uma semana, o valor de chamadas por consentimento/mês em "Como evolui?" é igual ao de "Quem lidera?" (escala por consentimento) e ao cartão da aba da instituição; trocar para volume devolve os números e blocos de antes da feature.

### Tests for User Story 2

- [ ] T009 [P] [US2] Em `dashboard/tests/test_v2_evolution.py`, teste HTTP de `GET /api/v2/evolution?metric=api&scale=per_consent`: `scale == "per_consent"`, `share_available == false`, `series[].shares` nulos, `group_share`, `group_share_change` e `share_changes` vazios, `headline.top_gainer` e `top_loser` nulos, `ecosystem_series.values` com o mesmo comprimento de `points`, e o valor de uma instituição em uma semana igual ao `per_consent_month` de `GET /api/v2/ranking?metric=api&scale=per_consent` para a mesma semana (SC-002). Incluir semana sem únicos: ponto nulo, nunca 0.
- [ ] T010 [P] [US2] Em `dashboard/tests/test_v2_evolution.py`, testes de erro e de regressão: `scale=per_consent` com `metric=unique_pf` → 422; `scale=xyz` → 422; chamada sem `scale` devolve `scale == "total"`, `share_available == true` e os mesmos valores de antes da mudança.

### Implementation for User Story 2

- [ ] T011 [US2] Em `dashboard/routers/v2.py`, adicionar o parâmetro `scale` a `evolution()` (reutilizar `_SCALES` e a regra do `/ranking`: válido só com `metric=api`, senão 422). Com `per_consent`, montar a série por instituição com `M.per_consent_30d(chamadas, únicos)` usando `M.load_metric("unique_total")`, e o ecossistema com `M.paired_sums` seguido de `per_consent_30d`; usar `M.growth_stock` sobre a série por consentimento para `headline.ecosystem_growth` e `series[].growth` (research.md, Decisões 4 e 5).
- [ ] T012 [US2] Em `dashboard/routers/v2.py`, completar a resposta de `evolution()` para `scale=per_consent` conforme `contracts/v2-api-delta.md` seção 2: acrescentar `scale`, `share_available` e `ecosystem_series`; zerar `series[].shares`, `group_share`, `group_share_change`, `share_changes`, `top_gainer` e `top_loser`; calcular `quarterly_pace` e `ecosystem_quarterly_pace` sobre a série mensal por consentimento. Sem `scale` ou com `total`, a resposta fica idêntica à atual mais os dois campos novos. Depende de T011.
- [ ] T013 [US2] Em `dashboard/gui/v2/evolucao.html`, adicionar o estado `scale` (padrão `per_consent` para a métrica de API, salvo em `opf:v2:filters` como `evo_scale`, preservando os campos de outras páginas), o seletor "Por consentimento/mês · Volume (30 dias)" visível só com a métrica de API, o envio de `scale` na consulta (linha ~183) e os textos de título, subtítulo e unidade (`NOUN`, `SHORT`, rodapé da linha ~315) para a escala por consentimento, com valores formatados com casas decimais. Depende de T005.
- [ ] T014 [US2] Em `dashboard/gui/v2/evolucao.html`, desenhar `ecosystem_series` como linha de referência no gráfico de linhas quando a escala é por consentimento (cor de tema, não hex de dado) e atualizar os cartões de topo para mostrar o crescimento do ecossistema e, no lugar de "ganhou/perdeu", a explicação de que participação não se aplica. Depende de T013.
- [ ] T015 [US2] Em `dashboard/gui/v2/evolucao.html`, quando `d.share_available` for falso, desativar o alternador "participação %", os blocos "Participação por grupo, mês a mês" e "Quem ganhou e quem perdeu espaço" com o texto "Participação não se aplica a chamadas por consentimento"; o gráfico de linhas, os cartões de crescimento e o ritmo trimestral continuam ativos. Depende de T013.
- [ ] T016 [US2] Em `dashboard/gui/v2/evolucao.html`, fazer a exportação de imagem e de CSV (linhas ~405–419) citarem a escala no título, subtítulo e nas colunas (FR-011). Depende de T013.
- [ ] T017 [US2] Validar no navegador o roteiro "Escala por consentimento" de `quickstart.md`, incluindo o passo de igualdade com "Quem lidera?" e com o cartão da aba da instituição (SC-002) e o retorno ao volume (SC-005).

**Checkpoint**: US1 e US2 funcionam de forma independente.

---

## Phase 5: User Story 3 - Ver para que a instituição usa os dados por endpoint (Priority: P3)

**Goal**: No bloco "Para que usa os dados", o usuário alterna para "Por endpoint", escolhe uma API e vê todos os endpoints dela, com a soma fechando com o total da API na visão por grupo.

**Independent Test**: Abrir uma instituição, alternar para "Por endpoint", escolher uma API e conferir que a soma dos endpoints (mais "Sem endpoint identificado") é igual ao total dessa API na visão por grupo para a mesma janela de 4 semanas.

### Tests for User Story 3

- [ ] T018 [P] [US3] Criar `data-loader/tests/test_api_endpoint_weekly.py` (SQLite real em arquivo temporário via `scrapers.open_db`, como `test_api_status_weekly.py`) cobrindo: soma só de `status = 200`; exclusão da API `consents`; linhas por endpoint e linha `endpoint_id = 0` quando o agregado é maior que a soma dos endpoints; nenhuma linha `endpoint_id = 0` quando fecham ou quando não há agregado; invariante I1 (fechamento por data × receptor × API); invariante I2 (soma por grupo de API igual a `api_group_weekly.req_week`); idempotência (rodar o refresh duas vezes dá as mesmas linhas, I4).
- [ ] T019 [P] [US3] Em `dashboard/tests/v2_fixtures.py`, acrescentar o DDL de `api_endpoint_weekly` e de `endpoint_history` e dados sintéticos: ao menos uma API com 3 endpoints dos quais um sem uso em uma instituição, uma API com parcela sem endpoint identificado, e uma API do grupo `Resource`. Manter a variante de "base antiga" sem essas tabelas para o teste de indisponibilidade.
- [ ] T020 [P] [US3] Em `dashboard/tests/test_v2_institution.py`, testes HTTP de `GET /api/v2/institution/{uuid}/endpoints`: caminho feliz (lista `apis` sem `Resource` e ordenada por volume, `api` padrão igual à de maior volume, `endpoints` ordenados por `calls_30d` decrescente, endpoint sem uso ao final com `used = false`, soma de `calls_30d` igual a `total.calls_30d`, participações somando 1, linha "Sem endpoint identificado" presente); `compare=group` e `compare=<outra instituição>`; erros: UUID inexistente → 404, `api` fora da lista → 422, `compare` inválido → 422; base sem `api_endpoint_weekly` → 200 com `unavailable == ["endpoints"]`.

### Implementation for User Story 3 — dados (`data-loader`)

- [ ] T021 [US3] Em `data-loader/scrapers.py`, na `open_db()`, criar a tabela `api_endpoint_weekly` (colunas e chave primária de `data-model.md`) com `CREATE TABLE IF NOT EXISTS` e os índices `(date)` e `(receptor_uuid, date)`, ao lado de `api_status_weekly` (linhas ~392 e ~457).
- [ ] T022 [US3] Em `data-loader/scrapers.py`, criar `refresh_api_endpoint_weekly(con) -> None` logo após `refresh_api_status_weekly` (linha ~513), seguindo a regra de preenchimento de `data-model.md`: apaga e reinsere tudo com `executescript`; linhas de endpoint de `api_requests` com `status = 200` e `api <> 'consents'`; linha `endpoint_id = 0` com `MAX(0, agregado − soma dos endpoints)` só quando maior que zero e quando existe agregado. Depende de T021.
- [ ] T023 [P] [US3] Em `data-loader/collector.py`, chamar `scrapers.refresh_api_endpoint_weekly` ao lado dos outros dois refreshes (linhas ~421–427) e atualizar as mensagens de log. Depende de T022.
- [ ] T024 [P] [US3] Em `data-loader/compute_signals.py`, chamar `scrapers.refresh_api_endpoint_weekly(con)` em `compute()` (linha ~101), medir o tempo como já é feito com `status_secs` e registrá-lo no resumo e no log. Depende de T022.

### Implementation for User Story 3 — API e tela (`dashboard`)

- [ ] T025 [US3] Em `dashboard/services/v2_metrics.py`, criar `load_endpoint_weekly()` (série longa `date`, `uuid`, `api`, `endpoint_id`, `endpoint`, `value` de `api_endpoint_weekly`) e `load_endpoint_catalog()` (último rótulo por `(api, endpoint_id)` de `endpoint_history`), no mesmo padrão de `load_api_groups` (levantar `TableMissing` quando a tabela não existir, cache pela mtime do banco). Anotar tipos nas assinaturas.
- [ ] T026 [US3] Em `dashboard/routers/v2.py`, criar `GET /api/v2/institution/{uuid}/endpoints` conforme `contracts/v2-api-delta.md` seção 3, reaproveitando a validação de `compare`, `M.ref_members`, `M.paired_sums`, `M.per_30_days` e o mapa `API_GROUPS` (sem `Resource`); a lista de endpoints une o catálogo com os endpoints vistos; incluir a linha `endpoint_id = 0` renomeada para "Sem endpoint identificado"; tratar `TableMissing` com `unavailable: ["endpoints"]`. Extrair a validação de `compare` para função só se a duplicação com `institution()` passar de 10 linhas. Depende de T025.
- [ ] T027 [US3] Em `dashboard/gui/v2/instituicao.html`, adicionar ao bloco "Para que usa os dados" o seletor "Por grupo de API · Por endpoint" (padrão por grupo, estado só em memória e não persistido), a chamada sob demanda ao endpoint novo ao escolher "Por endpoint" ou trocar de API (reaproveitando `compare` e a unidade do seletor já existente), o seletor de API com agrupamento e cor do grupo (cores vindas de `V2.meta.api_groups`), a lista completa de endpoints com barras da instituição e do comparado, a linha "Sem endpoint identificado", os endpoints sem uso atenuados ao final, a mensagem de "sem chamadas" e a de indisponibilidade quando `unavailable` vier preenchido. Manter a escolha ao trocar de instituição ou comparação (se a nova instituição não usa a API, vale a de maior volume). Depende de T026.
- [ ] T028 [US3] Em `dashboard/gui/v2/instituicao.html`, fazer a exportação de imagem e de CSV do bloco refletirem a visão por endpoint (colunas: API, endpoint, valor da instituição, participação, valor do comparado), conforme `contracts/v2-api-delta.md` seção 4. Depende de T027.
- [ ] T029 [US3] Rodar `compute_signals.py` na base local para criar e preencher `api_endpoint_weekly`, anotar o tempo de reconstrução medido (a estimativa do plano é 10 a 20 s) e executar a consulta de conferência do passo 1 do `quickstart.md` (esperado: nenhuma linha com `tab > agg`). Depende de T022 e T024.
- [ ] T030 [US3] Validar no navegador o roteiro "Visão por endpoint" de `quickstart.md`, incluindo a conferência de SC-003 (soma dos endpoints igual ao total da API na visão por grupo nas unidades "API total" e "%"), a volta ao padrão ao trocar de aba e o comportamento com uma base sem a tabela nova. Depende de T028 e T029.

**Checkpoint**: As três histórias funcionam de forma independente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentação, regressão e publicação.

- [ ] T031 [P] Atualizar `CLAUDE.md`: acrescentar `api_endpoint_weekly` à lista de tabelas derivadas (e ao comando `compute_signals.py`), `GET /api/v2/institution/{uuid}/endpoints` e o parâmetro `scale` de `/api/v2/evolution` à seção do Dashboard 2.0, e o período "Desde o começo do ano" às regras compartilhadas.
- [ ] T032 Rodar as suítes completas de `dashboard/` e `data-loader/` e comparar com a linha de base do T001 (SC-005): nenhum teste pré-existente pode falhar por causa da feature.
- [ ] T033 Executar o `quickstart.md` do início ao fim e confirmar SC-001 a SC-006 da spec, anotando qualquer divergência.
- [ ] T034 Abrir os PRs por fase contra `main` (US1, US2, US3), cada um com a descrição do que muda e do que foi testado. Para a US3, avisar na descrição que o deploy exige `compute_signals.py` e `./deploy.sh` (sync da base) antes de a visão por endpoint aparecer com dados; antes disso a tela mostra a mensagem de indisponível.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: vazia; nada bloqueia as histórias.
- **User Stories (Phases 3 a 5)**: dependem só do T001. A ordem recomendada é P1 → P2 → P3.
- **Polish (Phase 6)**: depende das histórias que forem entregues.

### User Story Dependencies

- **US1 (P1)**: independente. Só frontend.
- **US2 (P2)**: independente do US1 no comportamento, mas edita o mesmo arquivo (`evolucao.html`); T013 depende de T005 para evitar conflito.
- **US3 (P3)**: independente de US1 e US2. As tarefas de dados (T021–T024) podem andar em paralelo com US1 e US2; a tela (T027–T028) depende do endpoint (T026) e, para o teste manual, da tabela preenchida (T029).

### Within Each User Story

- Testes primeiro, devem falhar antes da implementação.
- Dados antes da API, API antes da tela.
- Validação manual por último.

### Parallel Opportunities

- US1: T004, T005 e T006 (três páginas diferentes) depois do T003.
- US2: T009 e T010 (mesmo arquivo de teste, mas casos independentes; rodar em sequência se houver conflito de edição).
- US3: T018, T019 e T020 em paralelo; T023 e T024 em paralelo depois do T022.
- Dados da US3 (T021–T024) em paralelo com o frontend da US1.

---

## Parallel Example: User Story 1

```bash
# Depois do T003 (shell.js), as três páginas podem ser migradas juntas:
Task: "Migrar index.html para V2.PERIODS / V2.periodStart"
Task: "Migrar evolucao.html para V2.PERIODS / V2.periodStart"
Task: "Migrar instituicao.html para V2.PERIODS / V2.periodStart"
```

## Parallel Example: User Story 3

```bash
# Testes e fixtures, antes da implementação:
Task: "Teste de integração do refresh em data-loader/tests/test_api_endpoint_weekly.py"
Task: "Fixtures do endpoint em dashboard/tests/v2_fixtures.py"
Task: "Testes HTTP do endpoint novo em dashboard/tests/test_v2_institution.py"

# Depois do refresh (T022):
Task: "Chamar o refresh em data-loader/collector.py"
Task: "Chamar o refresh em data-loader/compute_signals.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar T001.
2. Completar a Phase 3 (US1).
3. **Parar e validar**: período anual nas três abas, períodos antigos intactos.
4. Publicar com `./deploy.sh --skip-sync` (só código, sem trocar a base).

### Incremental Delivery

1. US1 → validar → PR e deploy (sem base nova).
2. US2 → validar → PR e deploy (sem base nova; só muda o `/evolution` e a tela).
3. US3 → dados primeiro (T021–T024 e T029), depois API e tela; PR e deploy exigem `compute_signals.py` e sync da base.
4. Cada história agrega valor sem quebrar as anteriores.

### Parallel Team Strategy

Com mais de uma pessoa: uma na US1 e na US2 (frontend e `/evolution`), outra nos dados da US3 (`data-loader`); a tela da US3 entra quando o endpoint estiver pronto.

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- O label [Story] liga cada tarefa à história da spec.
- Valores de tela existentes não podem mudar, exceto a escala inicial da métrica de API em "Como evolui?" (SC-005).
- Nenhuma coleta nova é necessária; a tabela nova é derivada de `api_requests`.
- Fora de escopo: período livre escolhido pelo usuário, mudanças no ranking de "Quem lidera?" e emenda da menção a `deploy.ps1` na Constituição.
