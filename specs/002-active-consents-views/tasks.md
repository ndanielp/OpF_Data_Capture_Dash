# Tasks: Visões de Consentimentos Ativos no Dashboard

**Input**: Design documents from `specs/002-active-consents-views/`

**Prerequisites**: plan.md ✓ | spec.md ✓ | research.md ✓ | data-model.md ✓ | contracts/ ✓ | quickstart.md ✓

**Tests**: Incluídos — exigidos pela Constituição II (HTTP-level test para todo endpoint FastAPI novo).

**Organization**: Tarefas agrupadas por User Story para permitir implementação e validação independente de cada história.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: User Story à qual a tarefa pertence (US1–US5)
- Todos os caminhos de arquivo são relativos à raiz do repositório

---

## Phase 1: Setup (Infraestrutura Compartilhada)

**Purpose**: Criar o esqueleto do router, a página HTML base e registrar o router no servidor. Bloqueia todas as fases seguintes.

- [x] T001 [P] Criar `dashboard/routers/active_consents.py` — módulo vazio com `router = APIRouter()`, imports base (`fastapi`, `sqlite3`, `config`, `services.constants.BRAND_COLORS`), helpers privados `_db_con()` (copiar padrão com PRAGMAs de `server.py`) e `_build_color_map()` (importar lógica de `server.py` ou replicar com `BRAND_COLORS` + `_FALLBACK_COLORS`)

- [x] T002 [P] Criar `dashboard/gui/active_consents.html` — estrutura HTML base com: `<nav>` com links para `/`, `/profile`, `/active-consents`; seções placeholder `#section-evolution`, `#section-matrix`, `#section-ranking`, `#section-intensity`; painel de filtros com `<input>` de período (`start`/`end`) e campo de receptor; `<script src="chart.js CDN">` e bloco `<script>` vazio; CSS inline mínimo (ou `<link>` para folha de estilos existente se houver)

- [x] T003 Registrar o router e infraestrutura em `dashboard/server.py`: (a) `from routers import active_consents as ac_router` + `app.include_router(ac_router.router, prefix="/api/active-consents")`; (b) `@app.get("/active-consents")` servindo `active_consents.html`; (c) função `_ensure_active_consents_indexes()` criando `idx_active_date_receptor` e `idx_active_date_transmitter` (padrão de `_ensure_dashboard_indexes()`); (d) chamar `_ensure_active_consents_indexes()` no `lifespan` após `_ensure_dashboard_indexes()`

**Checkpoint**: `uvicorn dashboard/server.py` sobe sem erro; `GET /active-consents` retorna 200 com HTML; `GET /api/active-consents/evolution` retorna 404 (rota ainda não implementada — esperado nesta fase).

---

## Phase 2: Foundational (Infraestrutura de Testes)

**Purpose**: Fixture de banco de dados de teste isolado com dados realistas em `active_consents` e `unique_consents`. Necessário antes de qualquer tarefa de teste.

**⚠️ CRITICAL**: Sem esta fase, nenhuma tarefa de teste pode ser executada.

- [x] T004 Criar `tests/test_active_consents_api.py` — arquivo com: (a) fixture `db_with_data(tmp_path)` que cria SQLite com `CREATE TABLE active_consents` + `CREATE TABLE unique_consents` e insere 2 receptores × 3 transmissores × 2 semanas de dados (ex.: datas `2026-05-12` e `2026-05-19`); (b) fixture `override_db(db_with_data, monkeypatch)` que substitui `config.DB_PATH` pelo caminho do DB de teste; (c) helper `async_client(override_db)` usando `httpx.AsyncClient(transport=ASGITransport(app=app))`; (d) um teste de fumaça `test_server_healthy` que verifica `GET /` retorna 200

**Checkpoint**: `pytest tests/test_active_consents_api.py::test_server_healthy` passa.

---

## Phase 3: US1 — Evolução Temporal (Priority: P1) 🎯 MVP

**Goal**: Gráfico de linhas mostrando a evolução semanal de consentimentos ativos, alternável entre receptor e transmissor, com filtro de período.

**Independent Test**: Dado DB com 2 semanas de dados para 2 receptores × 3 transmissores, `GET /api/active-consents/evolution?by=receptor` retorna 2 séries com 2 pontos cada. A página `/active-consents` renderiza o gráfico sem erros de console.

### Testes para US1

- [x] T005 [P] [US1] Adicionar em `tests/test_active_consents_api.py`: `test_evolution_by_receptor_happy_path` — verifica shape do JSON (`labels`, `series`, `by`), contagem de séries e que values têm comprimento igual a `labels`; `test_evolution_by_transmitter` — verifica agrupamento correto por transmissor; `test_evolution_empty_period` — período sem dados retorna `series=[]` e status 200; `test_evolution_receptor_filter` — `receptors="Bradesco"` filtra séries

### Implementação de US1

- [x] T006 [US1] Implementar `GET /evolution` em `dashboard/routers/active_consents.py` — parâmetros: `start: str`, `end: str`, `by: str = "receptor"`, `receptors: Optional[str]`; queries SQL de `data-model.md` (sum por receptor+date OU transmitter+date conforme `by`); agrupar em dicionário `{name: {date: total}}`; retornar `{"labels": [...], "series": [{name, color, values}], "by": by}`; `values[i]` = `null` se semana ausente para aquela série; cores via `_build_color_map()`

- [x] T007 [US1] Implementar gráfico de evolução em `dashboard/gui/active_consents.html` — função `loadEvolution(by)` que faz fetch de `/api/active-consents/evolution?by={by}&start=...&end=...&receptors=...`; cria/atualiza Chart.js `type: "line"` com `datasets` mapeados de `series`; seletor de rádio "Por receptor / Por transmissor" chama `loadEvolution` com o valor correspondente; conectar ao painel de filtros de período (evento `change` nos `<input>` de data)

**Checkpoint**: MVP completo. `GET /api/active-consents/evolution` retorna 200 com JSON correto. Página `/active-consents` exibe gráfico de linha com séries coloridas, alternável entre receptor e transmissor.

---

## Phase 4: US2 — Matriz Receptor × Transmissor (Priority: P2)

**Goal**: Heatmap HTML mostrando o volume de consentimentos ativos por par receptor × transmissor para a semana mais recente.

**Independent Test**: Dado DB com 2 receptores × 3 transmissores × 2 semanas, `GET /api/active-consents/matrix` retorna matriz `2×3` com `values[0][0]` igual ao total do par (receptor[0], transmitter[0]). A tabela renderizada na página tem células com intensidade de cor proporcional ao valor.

### Testes para US2

- [x] T008 [P] [US2] Adicionar em `tests/test_active_consents_api.py`: `test_matrix_shape` — verifica `len(values) == len(receptors)` e `len(values[0]) == len(transmitters)`; `test_matrix_values_correct` — verifica que `values[i][j]` é o total correto do par; `test_matrix_no_data` — período sem dados retorna `receptors=[], transmitters=[], values=[]`; `test_matrix_receptor_filter` — filtro de receptor reduz número de linhas

### Implementação de US2

- [x] T009 [US2] Implementar `GET /matrix` em `dashboard/routers/active_consents.py` — parâmetros: `end: str`, `receptors: Optional[str]`; query: `SELECT receptor, transmitter, total FROM active_consents WHERE date = (SELECT MAX(date) FROM active_consents WHERE date <= :end)`; pivotar em Python (dict de dict → listas `receptors`, `transmitters`, `values[][]`); pares ausentes preenchidos com 0; retornar `{receptors, transmitters, values, reference_date, max_value}`

- [x] T010 [US2] Implementar heatmap em `dashboard/gui/active_consents.html` — função `loadMatrix()` que faz fetch de `/api/active-consents/matrix`; gera `<table id="matrix-table">` programaticamente: primeira linha = cabeçalhos de transmissores (truncados com `title` para nomes longos), linhas seguintes = receptor + células; função `heatColor(value, maxValue)` → escala linear `rgb(r, g, 255)` (branco → azul); `<div id="matrix-tooltip">` posicionado com `mousemove` mostrando `receptor × transmitter: N`; scroll horizontal quando transmissores > viewport

**Checkpoint**: `GET /api/active-consents/matrix` retorna JSON correto. Tabela exibe células coloridas na página; tooltip aparece ao passar o cursor.

---

## Phase 5: US3 + US4 — Ranking com Δ% (Priority: P2/P3)

**Goal**: Ranking top-10 de receptores e transmissores com Δ% semana a semana. Inclui US4 (variação semanal) pois o endpoint /ranking já entrega `delta_pct`.

**Independent Test**: Dado DB com 2 semanas, `GET /api/active-consents/ranking?by=receptor` retorna items ordenados por `total` decrescente. Item com `total_prev=null` tem `delta_pct=null`. Página exibe barras com sinal "+" ou "−" no Δ%.

### Testes para US3 + US4

- [x] T011 [P] [US3] Adicionar em `tests/test_active_consents_api.py`: `test_ranking_receptor_order` — items ordenados por total decrescente; `test_ranking_transmitter` — agrupamento correto por transmissor; `test_ranking_delta_pct_correct` — dado receptor com prev=1000 e curr=1200, `delta_pct == 20.0`; `test_ranking_no_prev_week` — quando só existe 1 semana, `delta_pct == null` e `prev_date == null`; `test_ranking_limit` — `limit=3` retorna no máximo 3 items

### Implementação de US3 + US4

- [x] T012 [US3] Implementar `GET /ranking` em `dashboard/routers/active_consents.py` — parâmetros: `end: str`, `by: str = "receptor"`, `limit: int = 10`; query 1: `SELECT receptor/transmitter, SUM(total) FROM active_consents WHERE date = :latest GROUP BY ... ORDER BY ... DESC LIMIT :limit*2`; query 2: mesma query para `date = :prev_date` (semana imediatamente anterior disponível via `SELECT MAX(date) FROM active_consents WHERE date < :latest`); calcular `delta_pct` em Python; retornar `{items: [{name, total, total_prev, delta_pct, color}], reference_date, prev_date, by}`

- [x] T013 [US3] Implementar ranking em `dashboard/gui/active_consents.html` — função `loadRanking(by)` que faz fetch de `/api/active-consents/ranking?by={by}`; renderizar lista de itens como barras horizontais `<div style="width: {pct}%">` proporcionais ao maior `total`; exibir `delta_pct` com prefixo `+`/`−` e cor verde/vermelho; `null` exibido como "—"; toggle receptor/transmissor via seletor de rádio

**Checkpoint**: `GET /api/active-consents/ranking` retorna JSON correto com Δ%. Página exibe top-10 com barras e variação colorida.

---

## Phase 6: US5 — Intensidade de Uso (Priority: P3)

**Goal**: Razão consentimentos ativos ÷ clientes únicos por receptor para a semana mais recente. Identifica receptores com alta intensidade de uso por cliente.

**Independent Test**: Dado receptor A com 4.000 ativos e 2.000 únicos → `intensity = 2.0`. Receptor B sem dados em `unique_consents` → `intensity = null`, exibido como "—" na página.

### Testes para US5

- [x] T014 [P] [US5] Adicionar em `tests/test_active_consents_api.py`: `test_intensity_correct_value` — dado receptor com `active_total=4000` e `unique_total=2000`, `intensity == 2.0`; `test_intensity_null_when_no_unique` — receptor sem linha em `unique_consents` tem `intensity == null`; `test_intensity_null_when_zero_unique` — receptor com `unique_consents.total=0` tem `intensity == null`; `test_intensity_ordered_desc` — lista retornada em ordem decrescente de intensidade, com nulls no fim

### Implementação de US5

- [x] T015 [US5] Implementar `GET /intensity` em `dashboard/routers/active_consents.py` — parâmetros: `end: str`, `receptors: Optional[str]`; query SQL com LEFT JOIN (ver `data-model.md`): `SELECT a.receptor, SUM(a.total) AS active_total, u.total AS unique_total, CASE WHEN u.total > 0 THEN ROUND(1.0*SUM(a.total)/u.total, 1) ELSE NULL END AS intensity FROM active_consents a LEFT JOIN unique_consents u ON a.receptor_uuid=u.receptor_uuid AND a.date=? WHERE a.date=? GROUP BY ... ORDER BY intensity DESC NULLS LAST`; retornar `{items: [{receptor, active_total, unique_total, intensity, color}], reference_date}`

- [x] T016 [US5] Implementar gráfico de intensidade em `dashboard/gui/active_consents.html` — função `loadIntensity()` que faz fetch de `/api/active-consents/intensity`; renderizar barras horizontais com comprimento proporcional a `intensity` (valor máximo como referência); exibir `unique_total` e `active_total` como legenda de cada barra; células com `intensity == null` exibem "—" em vez de barra; ordenação decrescente já vem da API

**Checkpoint**: `GET /api/active-consents/intensity` retorna JSON correto. Página exibe gráfico de intensidade com "—" para receptores sem dados únicos.

---

## Phase 7: Polish e Validação

**Purpose**: Links de navegação, validação manual obrigatória (Constituição II) e verificação SQL pós-implementação.

- [x] T017 [P] Adicionar link `<a href="/active-consents">Consentimentos Ativos</a>` na barra de navegação de `dashboard/gui/dashboard.html`

- [x] T018 [P] Adicionar link `<a href="/active-consents">Consentimentos Ativos</a>` na barra de navegação de `dashboard/gui/receptor_profile.html`

- [ ] T019 Executar checklist de validação manual no browser conforme `specs/002-active-consents-views/quickstart.md` — verificar os 10 itens do checklist: carregamento da página, gráfico de evolução, seletor receptor/transmissor, matriz com tooltip, ranking com Δ%, intensidade com "—", filtro de período, ausência de erros HTTP 500

- [ ] T020 Executar queries SQL de verificação pós-implementação conforme `specs/002-active-consents-views/quickstart.md` — verificar contagem de rows, últimas 3 datas, top-20 pares por volume, intensidade de uso calculada para a semana mais recente

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 e T002 em paralelo; T003 depende de T001
- **Foundational (Phase 2)**: T004 depende de T003 (precisa da app registrada para o AsyncClient)
- **US1 (Phase 3)**: T005 e T006 em paralelo após T004; T007 depende de T006
- **US2 (Phase 4)**: T008 e T009 em paralelo após T004; T010 depende de T009
- **US3+US4 (Phase 5)**: T011 e T012 em paralelo após T004; T013 depende de T012
- **US5 (Phase 6)**: T014 e T015 em paralelo após T004; T016 depende de T015
- **Polish (Phase 7)**: T017 e T018 em paralelo após Phase 1; T019 após todas as fases de US; T020 após T019

### User Story Dependencies

- **US1 (P1)**: Pode iniciar após Phase 2 — sem dependência de outras USs
- **US2 (P2)**: Pode iniciar após Phase 2 — sem dependência de US1
- **US3+US4 (P2/P3)**: Pode iniciar após Phase 2 — sem dependência de outras USs
- **US5 (P3)**: Pode iniciar após Phase 2 — sem dependência de outras USs

As fases US2, US3 e US5 podem ser trabalhadas em paralelo após Phase 2.

### Parallel Opportunities

```bash
# Phase 1 — em paralelo:
T001: Criar dashboard/routers/active_consents.py
T002: Criar dashboard/gui/active_consents.html (estrutura base)

# Após T004 — todas as US em paralelo (se houver capacidade):
US1: T005+T006 (paralelos) → T007
US2: T008+T009 (paralelos) → T010
US3: T011+T012 (paralelos) → T013
US5: T014+T015 (paralelos) → T016
```

---

## Implementation Strategy

### MVP Completo (US1 apenas — Phases 1–3)

1. Phase 1: T001 → T002 (paralelo) → T003
2. Phase 2: T004
3. Phase 3: T005+T006 (paralelo) → T007
4. **PARAR e VALIDAR**: `GET /api/active-consents/evolution` retorna dados corretos; página exibe gráfico de linha funcional
5. Demonstrar e coletar feedback antes de continuar

### Entrega Incremental

1. Setup + Foundational → base pronta
2. US1 (evolução temporal) → demo do MVP
3. US2 (matriz) → visão de estrutura de mercado
4. US3+US4 (ranking + Δ%) → quem cresce, quem perde
5. US5 (intensidade) → profundidade analítica
6. Polish → links de navegação e validação final

---

## Notes

- **[P]** = arquivos diferentes, sem dependência de tarefa incompleta — podem rodar em paralelo
- **[Story]** mapeia a tarefa à User Story para rastreabilidade
- Cada US deve ser independentemente testável antes de avançar
- Testes HTTP-level são obrigatórios por Constituição II — não são opcionais aqui
- Validação manual do browser (T019) é obrigatória por Constituição II para qualquer mudança de UI
- Parar em qualquer checkpoint para validar a US independentemente antes de continuar
