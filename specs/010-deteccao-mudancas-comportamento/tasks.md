---
description: "Task list for 010-deteccao-mudancas-comportamento"
---

# Tasks: Módulo de Detecção de Mudanças de Comportamento

**Input**: Design documents from `/specs/010-deteccao-mudancas-comportamento/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/compute-signals-cli.md, contracts/signals-api.md, quickstart.md

**Tests**: Incluídos — a Constituição (Princípio II) exige teste de integração em SQLite real para toda nova escrita no banco, teste HTTP para todo endpoint novo e validação manual no navegador.

**Organization**: Agrupadas por user story. O cálculo (script) e a exibição (endpoint + card) são a base comum; cada história acrescenta a sua regra, seus testes, sua seção do card e sua validação contra a base real.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1 (novos entrantes), US2 (altas), US3 (quedas)

## Path Conventions

- Cálculo: `data-loader/` (único lado que escreve no banco)
- Leitura e exibição: `dashboard/`
- Constantes, regras e esquema: ver `data-model.md` — os valores numéricos NÃO devem ser reinventados nas tarefas.

---

## Phase 1: Setup

**Purpose**: Confirmar dependências e preparar os arquivos de teste.

- [X] T001 Confirmar que `data-loader/requirements.txt` (pandas, pytest) e `dashboard/requirements.txt` cobrem a feature sem dependência nova — nenhuma alteração esperada (plan.md, Technical Context)
- [X] T002 [P] Criar `data-loader/tests/test_signals.py` com fixture de SQLite em arquivo temporário contendo as tabelas `unique_consents`, `active_consents`, `api_requests` e `api_group_weekly` (DDL copiado de `scrapers.open_db`), e helpers para inserir séries semanais sintéticas; seguir o padrão de `data-loader/tests/test_active_consents_upsert.py`
- [X] T003 [P] Criar `dashboard/tests/test_signals_api.py` com fixture de SQLite temporário e `httpx.AsyncClient`, seguindo o padrão de `dashboard/tests/test_institution_groups.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Tabelas, script, endpoint e card vazios funcionando de ponta a ponta. Nenhuma regra de alerta ainda.

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase.

- [X] T004 Adicionar o DDL de `behavior_signals` (com `PRIMARY KEY (week, signal_type, metric, api_group, receptor_uuid)` e `api_group NOT NULL DEFAULT ''`), o índice `idx_behavior_signals_week` e a tabela `behavior_signals_run` (linha única, `CHECK (id = 1)`) em `scrapers.open_db()` em `data-loader/scrapers.py`, exatamente como em `data-model.md`
- [X] T005 Criar `data-loader/signals.py` com: as constantes da tabela de `data-model.md` no topo; um tipo `Signal` (NamedTuple ou dataclass tipada) com os campos da tabela; e funções de carga tipadas que devolvem as séries semanais por `receptor_uuid` de `unique_consents`, de `active_consents` (somado sobre transmissores) e de `api_group_weekly` (pivô por data de calendário, sem `Resource`), cada uma com o nome mais recente do receptor
- [X] T006 Implementar `api_coverage_ok(con) -> tuple[set[str], list[str]]` em `data-loader/signals.py`: por semana, total de chamadas (status 200, sem `consents`) de `api_requests` ≥ `API_COVERAGE_MIN` × mediana das 8 semanas anteriores; devolve semanas aprovadas e semanas bloqueadas (research.md, Decisão 3)
- [X] T007 Criar `data-loader/compute_signals.py` conforme `contracts/compute-signals-cli.md`: `open_db` → `scrapers.refresh_api_group_weekly` → trava de cobertura → lista de regras (vazia nesta fase) → numa única transação apagar `behavior_signals`, inserir as linhas e gravar `behavior_signals_run` (`computed_at`, `consents_through`, `api_through`, `api_skipped_weeks` em JSON, `signals_total`); logging no formato do projeto; saída 0 ou 1; rollback em erro
- [X] T008 [P] Teste de integração em `data-loader/tests/test_signals.py`: rodar `compute_signals` duas vezes sobre a mesma base produz exatamente as mesmas linhas; `behavior_signals_run` tem uma linha; `api_group_weekly` é reconstruída até a última semana de `api_requests` (reproduz o caso real de tabela defasada)
- [X] T009 Criar `dashboard/routers/signals.py` com `GET /` conforme `contracts/signals-api.md`: `week` (padrão = semana mais recente), `groups` (mesma semântica de `_parse_groups` da 009, resolvido com `services.of_analytics.resolve_institution_group`), lista `weeks` com contagem após o filtro, três seções sempre presentes com uma entrada por instituição ordenada por `volume`, `api_incomplete`, metadados de `behavior_signals_run`; tabela ausente → estrutura vazia com 200, sem criar a tabela
- [X] T010 Registrar o router em `dashboard/server.py` com `app.include_router(signals.router, prefix="/api/signals")`, junto dos routers existentes
- [X] T011 [P] Testes HTTP em `dashboard/tests/test_signals_api.py`: formato da resposta com as três seções; base sem `behavior_signals` → 200 vazio; `week` inexistente → seções vazias com `weeks` preenchido; `groups=incumbentes` remove instituições de outros grupos; várias linhas da mesma instituição viram uma entrada com vários `items`
- [X] T012 Criar o card "O que mudou" em `dashboard/gui/dashboard.html`: bloco `.chart-card` (id `card-signals`) logo após a `.date-bar`; seletor de semana alimentado por `weeks`; três seções (Novos entrantes, Altas, Quedas) renderizadas a partir de `sections`; mensagem explícita quando a semana não tem alertas; aviso quando `api_incomplete`; `setCardLoading('card-signals', …)` e mensagem de erro legível; cores só pelos tokens `--success`, `--error`, `--text-muted`
- [X] T013 Ligar o card aos filtros em `dashboard/gui/dashboard.html`: buscar `/api/signals` dentro de `_refreshNow()` passando `groups` de `buildParams()`; mudar o seletor de semana refaz só a busca do card; rótulos de grupo de API via `/api/of/api-groups`

**Checkpoint**: `python compute_signals.py` roda, o endpoint responde e o card aparece com "nenhuma mudança relevante" — base pronta para as regras.

---

## Phase 3: User Story 1 - Novos entrantes relevantes (Priority: P1) 🎯 MVP

**Goal**: Sinalizar o receptor recente que estreia com 30 mil ou mais, ou que passa de 30 mil crescendo 50% ou mais em 4 semanas.

**Independent Test**: Rodar o script sobre a base real e ver Banco Inter (6ª semana após a estreia), CloudWalk (3ª) e Shopee (estreia) como novos entrantes — e nenhum alerta para Google Pay, Midway ou BRB.

### Tests for User Story 1

- [X] T014 [P] [US1] Testes em `data-loader/tests/test_signals.py` com séries sintéticas: estreia com 271 que chega a 40 mil crescendo ≥50% em 4 observações → um `new_entrant` na semana esperada; estreia já ≥30 mil → alerta na estreia com `value_prev` NULL; crescimento rápido que fica abaixo de 30 mil → nenhum; receptor presente na primeira semana da série → nenhum; condição satisfeita de novo depois → continua uma única linha; cruzamento só após 26 semanas → nenhum

### Implementation for User Story 1

- [X] T015 [US1] Implementar `detect_new_entrants(...) -> list[Signal]` em `data-loader/signals.py` conforme a regra `new_entrant` de `data-model.md` (janela por posição na série do receptor, `t−4` limitado à estreia, base 0 conta como crescimento, primeira ocorrência apenas)
- [X] T016 [US1] Registrar `detect_new_entrants` na lista de regras de `data-loader/compute_signals.py` e preencher `volume` com os consentimentos únicos do receptor na semana
- [X] T017 [US1] Renderizar a seção "Novos entrantes" em `dashboard/gui/dashboard.html`: nome, grupo de instituição, volume atual e, quando houver, crescimento sobre a base de 4 semanas; estreia sinalizada como "estreia"
- [X] T018 [US1] Validar contra a base real conforme `quickstart.md` (passo 2): Inter, Shopee e CloudWalk nas semanas esperadas; Google Pay, Midway e BRB ausentes

**Checkpoint**: MVP — o card já mostra os novos entrantes relevantes, semana a semana.

---

## Phase 4: User Story 2 - Altas relevantes (Priority: P2)

**Goal**: Sinalizar altas de consentimentos (semana contra semana, +20%, imediato) e de uso de API (4 contra 4 semanas, descontado o ecossistema, +100%, confirmado por 2 semanas).

**Independent Test**: Na base real, a alta de CloudWalk em Contas (jul/2026) aparece; semanas de flutuação normal e altas gerais do ecossistema não aparecem.

### Tests for User Story 2

- [X] T019 [P] [US2] Testes de consentimentos em `data-loader/tests/test_signals.py`: receptor com ≥30 mil e mais de 26 semanas que sobe mais de 20% → `increase` na mesma semana, para `unique_consents` e `active_consents`; receptor com 26 semanas ou menos → nenhum; base abaixo de 30 mil → nenhum; +15% → nenhum
- [X] T020 [P] [US2] Testes de API em `data-loader/tests/test_signals.py`: receptor × grupo com base ≥1 milhão e razão relativa > 2,0 em 2 semanas seguidas → um único `increase` na segunda semana; só 1 semana → nenhum; a mesma alta em todo o ecossistema → nenhum (desconto); base abaixo de 1 milhão → nenhum; semana bloqueada pela trava de cobertura → nenhum

### Implementation for User Story 2

- [X] T021 [US2] Implementar `detect_consent_changes(series, metric) -> list[Signal]` em `data-loader/signals.py` com os limites `CONSENT_UP` e `CONSENT_DOWN` (as duas direções — a regra é simétrica; a US3 cobre os testes e a exibição de queda)
- [X] T022 [US2] Implementar `detect_api_changes(pivot, approved_weeks) -> list[Signal]` em `data-loader/signals.py`: médias móveis de 4 no eixo de calendário, razão relativa ao ecossistema do grupo, elegibilidade pela base, confirmação de 2 semanas com um alerta por evento, só em semanas aprovadas pela trava (as duas direções)
- [X] T023 [US2] Registrar `detect_consent_changes` (para `unique_consents` e `active_consents`) e `detect_api_changes` na lista de regras de `data-loader/compute_signals.py`
- [X] T024 [US2] Renderizar a seção "Altas" em `dashboard/gui/dashboard.html`: uma linha por instituição listando as métricas e os grupos de API afetados, com a variação de cada um
- [X] T025 [US2] Validar contra a base real (`data-loader/data/consents.db`, consulta do passo 2 de `quickstart.md`): alta de CloudWalk em Contas em jul/2026 presente; conferir que o total de alertas de API por semana fica perto de 2 em média (spec SC-003)

**Checkpoint**: Novos entrantes e altas funcionando juntos.

---

## Phase 5: User Story 3 - Quedas relevantes (Priority: P3)

**Goal**: Sinalizar quedas de consentimentos (−10%, imediato) e de uso de API (−40%, confirmado por 2 semanas), sem tratar ausência de histórico como queda.

**Independent Test**: Na base real aparecem as quedas de Belvo (fev/2026), Banco Safra (abr/2026 em consentimentos; jul/2026 em vários grupos de API, numa única linha) e Banco CSF (31/07/2026).

### Tests for User Story 3

- [X] T026 [P] [US3] Testes de consentimentos em `data-loader/tests/test_signals.py`: receptor elegível que cai mais de 10% → `decrease` na mesma semana; receptor sem semana anterior → nenhum; semana faltando na série → não vira queda
- [X] T027 [P] [US3] Testes de API em `data-loader/tests/test_signals.py`: razão relativa < 0,6 em 2 semanas seguidas → um `decrease` na segunda; receptor × semana ausente (NaN) não gera queda; semana bloqueada pela trava → nenhum e aparece em `api_skipped_weeks`

### Implementation for User Story 3

- [X] T028 [US3] Renderizar a seção "Quedas" em `dashboard/gui/dashboard.html`, com o mesmo formato de linha por instituição da seção "Altas"
- [X] T029 [US3] Validar contra a base real conforme `quickstart.md`: Belvo −37%, Banco Safra −47% e queda em vários grupos de API (uma linha no card), Banco CSF −83%/−87%

**Checkpoint**: As três seções funcionando.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T030 [P] Adicionar `python compute_signals.py` ao bloco de comandos do data-loader em `CLAUDE.md`, com a ordem `main.py run` → `compute_signals.py` → `deploy.ps1 -SyncOnly`
- [X] T031 [P] Revisar conformidade: nenhum hex novo em `dashboard/gui/dashboard.html` (Princípio III); `data-loader/` não importa nada de `dashboard/` (Princípio V); SQL parametrizado
- [X] T032 Rodar `data-loader/compute_signals.py` sobre a base real e medir: tempo de execução no log e `GET /api/signals` abaixo de 500 ms
- [X] T033 Executar `quickstart.md` do início ao fim, incluindo a validação do card no navegador (passo 5): seletor de semana, filtro de grupos, semana sem alertas

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as histórias
- **US1 (Phase 3)**: depende só da Foundational — é o MVP
- **US2 (Phase 4)**: depende da Foundational; independente da US1
- **US3 (Phase 5)**: depende da US2, porque reaproveita `detect_consent_changes` e `detect_api_changes`, que já emitem as duas direções
- **Polish (Phase 6)**: depois das histórias desejadas

### Within Phase 2

T004 → T005 → T006 → T007 → T008. Em paralelo a essa cadeia: T009 → T010 → T011, e T012 → T013 (arquivos diferentes do data-loader).

### Parallel Opportunities

- T002 e T003 (arquivos de teste diferentes)
- A cadeia do data-loader (T004–T008) em paralelo com a do dashboard (T009–T013)
- T014, T019, T020, T026 e T027 escrevem casos independentes no mesmo arquivo de teste — paralelos em conteúdo, mas convém escrevê-los em sequência para evitar conflito
- T030 e T031

---

## Parallel Example: Phase 2

```text
# Lado do cálculo:
Task: "DDL de behavior_signals em data-loader/scrapers.py"          (T004)
Task: "Constantes e cargas em data-loader/signals.py"               (T005)

# Lado da exibição, ao mesmo tempo:
Task: "Router GET /api/signals em dashboard/routers/signals.py"     (T009)
Task: "Card 'O que mudou' em dashboard/gui/dashboard.html"          (T012)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup + Foundational → script, endpoint e card vazios de ponta a ponta
2. US1 → novos entrantes no card
3. **PARAR e VALIDAR**: `quickstart.md`, passo 2 (Inter, Shopee, CloudWalk)
4. Publicar se estiver bom — já entrega o sinal de maior valor

### Incremental Delivery

1. Base → US1 (novos entrantes) → publicar
2. US2 (altas de consentimento e de API) → validar o volume de alertas → publicar
3. US3 (quedas) → validar Belvo, Safra e CSF → publicar
4. Polish

---

## Notes

- Os limites numéricos vivem só nas constantes do topo de `signals.py`; testes e código as referenciam, não repetem os números.
- `compute_signals.py` reconstrói o histórico inteiro a cada execução — não criar lógica incremental.
- O dashboard nunca cria nem altera `behavior_signals`; só lê e trata a ausência.
- Commitar ao fim de cada fase.
