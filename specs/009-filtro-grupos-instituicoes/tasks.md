---
description: "Task list for 009-filtro-grupos-instituicoes"
---

# Tasks: Filtro de Grupos de Instituições

**Input**: Design documents from `/specs/009-filtro-grupos-instituicoes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/institution-groups-api.md, quickstart.md, institution-groups-draft.md

**Tests**: Incluídos — Constitution Principle II exige teste HTTP-level para novo endpoint e para qualquer endpoint FastAPI alterado, além de validação manual no navegador.

**Organization**: Tarefas agrupadas por user story (spec.md) para permitir implementação e teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência entre si)
- **[Story]**: US1 (P1 — grupo único), US2 (P2 — multi-seleção), US3 (P3 — não classificados)

## Path Conventions

Feature inteiramente em `dashboard/` (ver plan.md § Project Structure). Sem alteração em `data-loader/`.

---

## Phase 1: Setup

**Purpose**: Confirmar que nenhuma dependência nova é necessária e preparar o arquivo de testes.

- [X] T001 Confirmar que `dashboard/requirements.txt` não precisa de novas dependências (stack já cobre FastAPI/pandas/httpx) — nenhuma alteração esperada
- [X] T002 [P] Criar `dashboard/tests/test_institution_groups.py` com import de `httpx.AsyncClient`/`server:app`, seguindo o padrão de `dashboard/tests/test_active_consents_api.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura compartilhada que TODAS as user stories dependem.

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa.

- [X] T003 [P] Adicionar constante `INSTITUTION_GROUPS` (lista de tuplas `(substring_lowercase, grupo_slug)`) em `dashboard/services/constants.py`, populada a partir de `specs/009-filtro-grupos-instituicoes/institution-groups-draft.md` (ver data-model.md)
- [X] T004 [P] Adicionar constantes `GROUP_LABELS` e `GROUP_COLORS` (4 cores novas, distintas de `API_GROUPS`) em `dashboard/services/constants.py`
- [X] T005 Implementar `resolve_institution_group(name: str) -> str` em `dashboard/services/of_analytics.py`, usando `INSTITUTION_GROUPS` (match por substring case-insensitive, primeiro vence, default `"outros"`) — depende de T003
- [X] T006 [P] Implementar `_parse_groups(groups_param: str | None) -> list[str] | None` em `dashboard/server.py`, espelhando `_parse_receptors` existente
- [X] T007 [P] Implementar `_parse_groups(groups_param: str | None) -> list[str] | None` em `dashboard/routers/active_consents.py`, espelhando `_parse_receptors` existente
- [X] T008 Implementar `GET /api/of/institution-groups` em `dashboard/routers/openfinance.py`, retornando `{groups: {...}, institutions: {...}}` conforme `contracts/institution-groups-api.md` — depende de T003, T004, T005
- [X] T009 [P] Teste HTTP para `GET /api/of/institution-groups` (formato da resposta, 4 grupos presentes, contagens > 0) em `dashboard/tests/test_institution_groups.py` — depende de T008

**Checkpoint**: Fundação pronta — as 3 user stories podem começar.

---

## Phase 3: User Story 1 - Focar análise em um único grupo (Priority: P1) 🎯 MVP

**Goal**: Usuário seleciona um grupo (ex.: Incumbentes) e a matriz, gráficos e rankings do dashboard passam a considerar só esse grupo, nas 3 páginas (Ecossistema, Perfil Receptores, Ativos).

**Independent Test**: Selecionar "Incumbentes" no filtro e verificar que matriz, gráficos e rankings recalculam considerando só esse grupo; limpar o filtro e ver que os dados voltam ao total geral.

### Tests for User Story 1

- [X] T010 [P] [US1] Teste HTTP: `GET /api/consents?groups=incumbentes` retorna só dados de instituições do grupo, em `dashboard/tests/test_institution_groups.py`
- [X] T011 [P] [US1] Teste HTTP: `GET /api/active-consents/matrix?groups=incumbentes` filtra AMBOS os eixos (linhas=receptor E colunas=transmissor) em `dashboard/tests/test_institution_groups.py`

### Implementation for User Story 1

- [X] T012 [US1] Adicionar parâmetro `groups` e filtragem em `get_consents` (`dashboard/server.py`) — depende de T005, T006
- [X] T013 [US1] Adicionar parâmetro `groups` e filtragem em `get_api_requests` (`dashboard/server.py`)
- [X] T014 [US1] Adicionar parâmetro `groups` e filtragem em `get_resources` (`dashboard/server.py`)
- [X] T015 [US1] Adicionar parâmetro `groups` e filtragem em `get_acceleration` (`dashboard/server.py`)
- [X] T016 [US1] Adicionar parâmetro `groups` e filtragem nos DOIS eixos (receptor e transmissor) em `matrix()` (`dashboard/routers/active_consents.py`) — depende de T005, T007
- [X] T017 [US1] Adicionar parâmetro `groups` e filtragem em `evolution()`, `ranking()`, `intensity()` (`dashboard/routers/active_consents.py`)
- [X] T018 [P] [US1] Adicionar seção `.sidebar-group "Grupos"` (lista de checkboxes, populada via `/api/of/institution-groups`) em `dashboard/gui/dashboard.html`, seguindo a estrutura de sidebar do Shell Contract (Principle VI §6.3)
- [X] T019 [P] [US1] Adicionar a mesma seção `.sidebar-group "Grupos"` em `dashboard/gui/receptor_profile.html`
- [X] T020 [P] [US1] Adicionar a mesma seção `.sidebar-group "Grupos"` em `dashboard/gui/active_consents.html`
- [X] T021 [US1] Implementar a lógica JS de seleção de grupo → dispara refresh + lê/escreve `sessionStorage['opf:filters'].groups` (spread preservando demais campos) nas 3 páginas — depende de T018, T019, T020
- [X] T022 [US1] Validação manual no navegador: passos 1–3 de `quickstart.md` (selecionar "Neo Banks" na Ecossistema, confirmar recálculo de matriz/gráficos/rankings; limpar filtro e confirmar retorno ao total)

**Checkpoint**: US1 funcional de ponta a ponta — grupo único filtra as 3 páginas corretamente.

---

## Phase 4: User Story 2 - Comparar múltiplos grupos (Priority: P2)

**Goal**: Usuário seleciona mais de um grupo simultaneamente (ex.: Incumbentes + Neo Banks) e vê a união dos dados.

**Independent Test**: Selecionar dois grupos e conferir que o resultado é a união dos dados de cada um filtrado individualmente; desmarcar um e ver recálculo só com o remanescente.

### Tests for User Story 2

- [X] T023 [P] [US2] Teste HTTP: `GET /api/consents?groups=incumbentes,neo_banks` retorna a união dos dois grupos (comparado à soma dos filtros individuais) em `dashboard/tests/test_institution_groups.py`

### Implementation for User Story 2

- [X] T024 [US2] Confirmar que a UI de checkboxes (T018–T020) permite múltiplas seleções simultâneas sem exclusividade — ajustar se necessário nas 3 páginas
- [X] T025 [US2] Adicionar indicador visível dos grupos ativos (chips) próximo à date-bar, refletindo a seleção atual de `groups`, nas 3 páginas — atende FR-007
- [X] T026 [US2] Validação manual no navegador: selecionar 2 grupos e confirmar união dos dados; desmarcar um e confirmar recálculo só com o remanescente (Acceptance Scenarios da US2 em spec.md)

**Checkpoint**: US1 e US2 funcionam juntas — multi-seleção de grupos funcional nas 3 páginas.

---

## Phase 5: User Story 3 - Identificar não classificados (Priority: P3)

**Goal**: Instituições sem classificação aparecem agrupadas como "Outros/Não classificado" em vez de sumirem ou quebrarem a visualização.

**Independent Test**: Instituição sem classificação aparece em "Outros" quando esse grupo é selecionado; selecionar todos os 4 grupos produz os mesmos totais que nenhum filtro aplicado.

### Tests for User Story 3

- [X] T027 [P] [US3] Teste HTTP: instituição sem match em `INSTITUTION_GROUPS` resolve para `"outros"` e aparece em `GET /api/consents?groups=outros` em `dashboard/tests/test_institution_groups.py`
- [X] T028 [P] [US3] Teste HTTP: `GET /api/consents?groups=incumbentes,neo_banks,itps,outros` produz totais idênticos a `GET /api/consents` sem `groups` (SC-003) em `dashboard/tests/test_institution_groups.py`

### Implementation for User Story 3

- [X] T029 [US3] Garantir que "Outros/Não classificado" sempre aparece como 4ª opção no filtro de Grupos (mesmo com contagem baixa) nas 3 páginas — depende de T018–T020
- [X] T030 [US3] Validação manual no navegador: confirmar que uma instituição sem classificação aparece em "Outros"; confirmar que os 4 grupos selecionados juntos batem com o total sem filtro (passo 6 de `quickstart.md`)

**Checkpoint**: Todas as 3 user stories funcionam de forma independente e combinada.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Consistência final e validação de conformidade com a Constituição.

- [X] T031 [P] Revisar que nenhuma cor de grupo está hardcoded fora de `dashboard/services/constants.py` (Principle III) — checagem manual em `dashboard/gui/*.html`
- [X] T032 [P] Revisar que `data-loader/` não foi tocado e nenhuma alteração de schema SQLite foi introduzida (Principle V)
- [X] T033 Executar `quickstart.md` do início ao fim como validação final de aceite

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA todas as user stories
- **User Story 1 (Phase 3)**: depende só do Foundational — é o MVP
- **User Story 2 (Phase 4)**: depende do Foundational; reaproveita a UI criada em US1 (T018–T020), mas os testes/critérios de aceite são independentes
- **User Story 3 (Phase 5)**: depende do Foundational; reaproveita a UI criada em US1, independente de US2
- **Polish (Phase 6)**: depende de todas as stories desejadas estarem completas

### Parallel Opportunities

- T003, T004 em paralelo (mesmo arquivo `constants.py`, mas blocos distintos e independentes — cuidado com conflito de merge se rodados por agentes diferentes; seguros para execução sequencial rápida)
- T006, T007 em paralelo (arquivos diferentes)
- T010, T011 em paralelo (mesmo arquivo de teste, casos independentes)
- T018, T019, T020 em paralelo (3 arquivos HTML diferentes)
- T023, T027, T028 podem rodar em paralelo entre si (mesmo arquivo de teste, casos independentes)

---

## Parallel Example: User Story 1

```bash
# Testes de US1 em paralelo:
Task: "Teste HTTP groups=incumbentes em /api/consents"
Task: "Teste HTTP groups=incumbentes em /api/active-consents/matrix (2 eixos)"

# UI das 3 páginas em paralelo:
Task: "Sidebar Grupos em dashboard/gui/dashboard.html"
Task: "Sidebar Grupos em dashboard/gui/receptor_profile.html"
Task: "Sidebar Grupos em dashboard/gui/active_consents.html"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Completar Phase 1 (Setup) e Phase 2 (Foundational)
2. Completar Phase 3 (US1) — grupo único filtrando as 3 páginas
3. **PARAR e VALIDAR**: rodar `quickstart.md` até o passo 3
4. Deploy/demo se pronto

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → multi-select ainda não confirmado, mas grupo único já entrega valor (MVP)
3. US2 → confirma união entre grupos + indicador visível
4. US3 → garante que "Outros" nunca some dados, fecha o critério SC-002/SC-003
5. Polish → checagem final de conformidade com a Constituição

---

## Notes

- [P] = arquivos diferentes, sem dependência
- [Story] mapeia a tarefa à user story correspondente
- Escrever os testes antes da implementação de cada story (Constitution Principle II)
- Rodar `quickstart.md` a cada checkpoint, não só no final
- Evitar: filtro de grupo com comportamento diferente entre as 3 páginas (viola Principle III)
