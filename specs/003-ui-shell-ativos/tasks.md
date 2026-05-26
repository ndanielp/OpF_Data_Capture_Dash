# Tasks: UI Shell Contract — Página Ativos

**Input**: Design documents from `specs/003-ui-shell-ativos/`

**Prerequisites**: plan.md ✓ | spec.md ✓

**Tests**: Não se aplicam testes HTTP-level (sem novos endpoints). Validação manual obrigatória por Constituição II (T014).

**Arquivo alvo único**: `dashboard/gui/active_consents.html` — refatoração completa de shell. Nenhum arquivo Python é alterado.

**Organization**: Tarefas organizadas por User Story. Todas operam no mesmo arquivo, portanto sem paralelismo de arquivo — mas a ordem lógica permite validação incremental a cada fase.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Seção CSS/HTML independente do JS — pode ser escrita em paralelo
- **[Story]**: User Story da spec.md à qual a tarefa pertence (US1–US5)

---

## Phase 1: Setup (CSS Foundation)

**Purpose**: Alinhar os design tokens e as classes de shell ao padrão canônico antes de alterar qualquer estrutura HTML. Bloqueia todas as fases seguintes.

- [x] T001 Substituir bloco `<style>` de `dashboard/gui/active_consents.html`: remover tokens divergentes (`--radius-sm/md/lg` com 6/10/16px e `--font-mono`) e substituir pelos canônicos (`--r-sm:4px`, `--r-md:8px`, `--r-lg:12px`; `--s1..s8`; `--tx-xs..xl`); adicionar override `[data-theme="light"]` idêntico ao `dashboard.html` (9 variáveis: `--bg-base:#F3F4F6` … `--border-default:#9CA3AF`); atualizar `body` para `height:100vh; display:flex; flex-direction:column; overflow:hidden; -webkit-font-smoothing:antialiased` (remover `min-height:100vh`)

- [x] T002 [P] Adicionar ao `<style>` de `dashboard/gui/active_consents.html` as classes do shell que ainda não existem: `.titlebar` (38px, `--bg-elevated`, border-bottom, flex, align-center, padding 0 `--s4`, gap `--s2`), `.titlebar-logo` (20×20px, `--text-accent` bg, `--r-sm`, 10px bold white), `.titlebar-name` (12px, weight 600), `.titlebar-spacer` (flex:1), `.theme-btn` (transparent border, 14px, hover `--bg-hover`), `.app-body` (flex:1, display:flex, overflow:hidden, min-height:0), `.main-content` (flex:1, overflow-y:auto, padding `--s5`, gap `--s5`, min-width:0) com scrollbar customizado (width 6px)

**Checkpoint**: Tokens e classes shell definidas. `body` compila sem conflitos de CSS.

---

## Phase 2: Foundational (HTML Shell Structure)

**Purpose**: Substituir o DOM macro (`<nav>` + `<main class="page">`) pelo shell canônico. Bloqueia US1 em diante.

**⚠️ CRITICAL**: Esta fase altera a estrutura raiz do arquivo. Todos os gráficos ficam temporariamente sem contexto de layout até T004.

- [x] T003 Substituir o elemento `<nav>` e o `<div class="page">` de `dashboard/gui/active_consents.html` pela estrutura canônica: `<div class="titlebar">` com logo badge "OF", span "Open Finance Brasil", separador `›` em `--text-muted`, nav-tab group (container com `background:rgba(0,0,0,0.1); padding:3px; border-radius:var(--r-md); border:1px solid var(--border-subtle)`) contendo os 3 links — `Ecossistema`→`/` (inativo), `Perfil Receptores`→`/profile` (inativo), `Ativos`→`/active-consents` (ativo: `font-weight:600; background:var(--bg-hover); box-shadow:0 1px 2px rgba(0,0,0,0.2)`), titlebar-spacer, `<button id="theme-toggle" class="theme-btn">☀️/🌙</button>`; criar `<div class="app-body">` com `<aside class="sidebar" id="sidebar">` vazio e `<main class="main-content" id="main-content">` contendo placeholder para o conteúdo existente

- [x] T004 Adicionar ao `<style>` de `dashboard/gui/active_consents.html` as classes de sidebar: `.sidebar` (width:224px, `--bg-surface`, border-right subtle, flex column, flex-shrink:0), `.sidebar-inner` (flex:1, overflow-y:auto, scrollbar 4px), `.sidebar-group` (padding `--s4`, border-bottom subtle), `.sidebar-group-header` (flex, space-between, margin-bottom `--s3`), `.sidebar-group-label` (11px, weight 700, `--text-muted`, uppercase, letter-spacing 0.1em), `.sidebar-group-badge` (11px, `--text-muted`, `--bg-elevated` pill, padding 1px 6px, border-radius 10px), `.sidebar-search` (width:100%, `--bg-elevated`, border `--border-default`, `--r-sm`, `--text-primary`, 12px, padding 5px `--s2`, focus border `--text-accent`), `.receptor-list` (list-style:none, max-height:240px, overflow-y:auto, scrollbar 3px), `.receptor-item` (flex, gap `--s2`, padding 5px `--s2`, `--r-sm`, cursor pointer, 12px, hover `--bg-hover`, `&.selected` bg `rgba(74,158,255,0.1)`, `&.inactive` color `--text-muted`), `.receptor-dot` (8×8px, border-radius 50%, flex-shrink:0; inactive usa `--border-default`), `.receptor-name` (overflow hidden, text-overflow ellipsis), `.sidebar-footer` (padding `--s4`, border-top subtle, flex-shrink:0), `.last-updated` (11px, `--text-muted`, flex, gap `--s1`), `.update-dot` (6px circle, `--success`), `.btn-refresh` (width:100%, `--bg-elevated`, border `--border-default`, `--text-secondary`, 12px, padding `--s2 --s4`, `--r-md`, hover `--bg-hover`); popular HTML do `<aside>` com: grupo "Receptores" (label + badge `id="receptor-count"` + search `id="receptor-search"` + `<ul id="receptor-list">`), sidebar-footer (`.last-updated` com `id="last-updated-text"` + `button.btn-refresh id="btn-refresh"`)

**Checkpoint**: `uvicorn server:app --port 8000` → `/active-consents` renderiza titlebar + sidebar vazia + main com filtros antigos empilhados verticalmente (antes do T007).

---

## Phase 3: US1 + US2 — Shell Funcional + Date Bar (Priority: P1) 🎯 MVP

**Goal**: Sidebar com receptores clicáveis, date bar com quick-range, theme toggle funcionando — shell completo e interativo.

**Independent Test**: Clicar em um receptor na sidebar filtra os gráficos; clicar "3m" atualiza todos os 4 gráficos; alternar tema persiste após reload.

### Implementação US1 — Receptor Sidebar + Theme Toggle

- [x] T005 [US1] Implementar JS de sidebar em `dashboard/gui/active_consents.html`: adicionar variáveis de estado `let _allReceptors = []; let _dbMinDate = null; let _dbMaxDate = null;`; função `loadReceptors()` que faz `fetch('/api/receptors')` e chama `buildReceptorList(data)`; função `buildReceptorList(receptors)` que popula `#receptor-list` com `<li class="receptor-item [inactive] [selected]">` contendo `.receptor-dot` (style `background:rec.color` se `rec.top`, senão sem background) e `.receptor-name`; click handler: sem Ctrl/Meta/Shift → deseleciona todos + seleciona o clicado → chama `refresh()`; com modifier → toggle o item → chama `refresh()`; input `#receptor-search` → filtra `li` por `dataset.label.toLowerCase().includes(q)` sem chamar `refresh()`; atualiza badge `#receptor-count`; `#btn-refresh` chama `refresh()`; chamar `loadReceptors()` no `DOMContentLoaded`

- [x] T006 [P] [US1] Implementar theme toggle JS em `dashboard/gui/active_consents.html`: ler `localStorage.getItem('theme') || 'dark'` no boot e setar `document.body.setAttribute('data-theme', currentTheme)` antes do primeiro render; click em `#theme-toggle` → alterna, seta `data-theme`, grava em localStorage; função `applyThemeColorsToCharts()` que atualiza `Chart.defaults.color` (light: `#4B5563`, dark: `#8B95B0`), `Chart.defaults.borderColor`, `gridColor` em `scales.*.grid.color` e `plugins.tooltip.*` de todos os charts ativos (`_lineChart`, `_matrixChart` não existe — apenas o `lineChart` de evolução), chama `chart.update()` em cada um

### Implementação US2 — Date Bar com Quick Ranges

- [x] T007 [P] [US2] Adicionar ao `<style>` de `dashboard/gui/active_consents.html` as classes de date-bar: `.date-bar` (`--bg-elevated`, border `--border-subtle`, `--r-md`, padding `--s2 --s4`, flex, align-center, gap `--s4`, flex-wrap, position:sticky, top:0, z-index:10), `.date-bar-label` (11px, weight 700, `--text-muted`, uppercase, letter-spacing 0.08em), `.date-inputs` (flex, gap `--s2`), `.date-field` (`--bg-surface`, border `--border-default`, `--r-sm`, `--text-primary`, 12px, padding 4px `--s2`, focus border accent, `color-scheme:dark`; light override `color-scheme:light`), `.date-arrow` (`--text-muted`, 13px), `.date-spacer` (flex:1), `.quick-ranges` (flex, gap `--s1`), `.quick-btn` (transparent bg, border `--border-default`, `--text-secondary`, 11px, padding 3px `--s2`, `--r-sm`, hover `--bg-hover`, `.active` bg `--text-accent`), `.chart-toggles` (flex, gap 2px, `--bg-elevated`, padding 2px, `--r-sm`, border subtle), `.chart-toggles button` (transparent, 11px, padding 4px 10px, `.active` bg `--bg-surface`, box-shadow 0 1px 2px); substituir `<div class="filter-bar">` antigo por `<div class="date-bar">` como primeiro filho de `#main-content`, contendo: label "PERÍODO", `.date-inputs` (date-start → date-end), `.date-spacer`, `.quick-ranges` (7d/30d/3m/6m/1a[active]/Ano atual/Tudo), `.date-spacer`, `.chart-toggles` com botões "Receptor" e "Transmissor" para o gráfico de evolução

- [x] T008 [US2] Implementar JS do date bar em `dashboard/gui/active_consents.html`: função `today()` retorna `new Date().toISOString().slice(0,10)`; função `loadDbRange()` que faz `fetch('/api/stats')` e preenche `_dbMinDate`/`_dbMaxDate` e os atributos `min`/`max` dos inputs; IIFE de init que seta `date-start` para 1 ano atrás e `date-end` para hoje; quick-btn click: remove `.active` de todos → adiciona no clicado → calcula `startDate` baseado em `_dbMaxDate || today()` com lógica: `"0"` → `_dbMinDate || '2020-01-01'`, `"ytd"` → `endDate.slice(0,4)+'-01-01'`, float < 1 → `d.setDate(d.getDate() - Math.round(months*30))`, float ≥ 1 → `d.setMonth(d.getMonth()-months)` → seta inputs → chama `refresh()`; inputs `change` → remove `.active` de quick-btns → chama `refresh()`; `.chart-toggles` buttons click → toggle `.active` → atualiza `currentBy` (`'receptor'|'transmitter'`) → chama `loadEvolution()`; chamar `loadDbRange()` no `DOMContentLoaded`

**Checkpoint**: MVP shell completo. Sidebar com receptores clicáveis, date bar com quick-range, theme toggle, todos os gráficos recarregam ao mudar receptor ou período.

---

## Phase 4: US3 — Loading States por Card (Priority: P1)

**Goal**: Cada um dos 4 cards exibe a sweep animation enquanto carrega, com canvas/table em 35% opacidade.

**Independent Test**: Ao clicar em um receptor, os 4 cards mostram a linha azul animada simultaneamente e voltam ao normal ao receber resposta.

- [x] T009 [US3] Adicionar ao `<style>` de `dashboard/gui/active_consents.html` as classes de chart-card: `.chart-card` (`--bg-surface`, border `--border-subtle`, `--r-lg`, padding `--s5`, position:relative, overflow:hidden), `.chart-card.card-loading::after` (content:'', position:absolute, top:0, left:-60%, width:60%, height:2px, gradient `transparent → --text-accent → transparent`, animation `card-sweep 1.1s linear infinite`), `@keyframes card-sweep {to{left:110%}}`, `.chart-card.card-loading canvas, .chart-card.card-loading table {opacity:0.35; transition:opacity 0.12s}`, `.chart-head` (flex, space-between, align-items:flex-start, margin-bottom `--s5`, gap `--s4`), `.chart-title` (17px, weight 600), `.chart-subtitle` (12px, `--text-secondary`, margin-top 3px), `.chart-empty` (flex, align-center, justify-center, height:120px, `--text-muted`, 12px); refatorar as 4 seções de conteúdo: substituir cada `<div class="card">` por `<div class="chart-card" id="card-[nome]">` mantendo o mesmo `id` referenciado no JS; substituir `.card-header`/`.card-title`/`.card-subtitle` por `.chart-head`/`.chart-title`/`.chart-subtitle`; adicionar `<div class="chart-empty" style="display:none">Sem dados</div>` acima de cada canvas/table

- [x] T010 [US3] Adicionar função `setCardLoading(id, on)` em `dashboard/gui/active_consents.html`: `const el = document.getElementById(id); if(el) el.classList.toggle('card-loading', on);`; adicionar chamadas em `loadEvolution()`: `setCardLoading('card-evolution', true)` no início do fetch, `setCardLoading('card-evolution', false)` no finally; idem para `loadMatrix()` (`card-matrix`), `loadRanking()` (`card-ranking`), `loadIntensity()` (`card-intensity`); tratar estados vazios: se resposta vazia, mostrar `.chart-empty` e esconder canvas/table

**Checkpoint**: Os 4 cards exibem loading sweep ao carregar e estado vazio quando não há dados no período.

---

## Phase 5: US4 + US5 — sessionStorage + Status Bar (Priority: P2)

**Goal**: Filtros persistem entre navegações; status bar mostra a data de referência dos dados.

**Independent Test**: Selecionar receptor + período, navegar para Ecossistema, voltar para Ativos → filtros restaurados. Status bar mostra a data da semana mais recente disponível.

- [x] T011 [P] [US4] Implementar persistência sessionStorage em `dashboard/gui/active_consents.html`: na IIFE de init, após setar defaults, ler `JSON.parse(sessionStorage.getItem('opf:filters') || 'null')`; se existir, sobrescrever `date-start` com `saved.start` e `date-end` com `saved.end`, e pré-selecionar receptores de `saved.receptors` (split por vírgula, comparar com `dataset.label`); em `refresh()` (ou no ponto de disparo), gravar `sessionStorage.setItem('opf:filters', JSON.stringify({...prev, start, end, receptors}))` onde `prev` é lido via `JSON.parse(sessionStorage.getItem('opf:filters') || '{}')` para preservar campos de outras páginas (`status`, `normalize`, `institution`); `receptors` = nomes selecionados join(',') ou string vazia

- [x] T012 [P] [US5] Adicionar ao `<style>` de `dashboard/gui/active_consents.html` as classes `.status-bar` (`--bg-elevated`, border-top `--border-subtle`, padding 0 `--s5`, height:28px, flex, align-center, gap `--s5`, flex-shrink:0, 11px, `--text-muted`), `.status-item` (flex, align-center, gap `--s1`), `.status-value` (`--text-secondary`, weight 500), `.status-pill` (rgba green 0.15 bg, `--success` color, padding 1px 6px, border-radius 10px, 10px, weight 600); adicionar HTML `<div class="status-bar">` após `.app-body`: `<div class="status-item">Referência <span class="status-value" id="stat-ref">—</span></div>`, `<span class="status-pill">ONLINE</span>`; atualizar `#stat-ref` no JS com o `reference_date` retornado por qualquer endpoint após load bem-sucedido (usar o do `/ranking` por ser sempre disponível)

**Checkpoint**: Filtros sobrevivem a navegações entre páginas. Status bar mostra data da última semana disponível no banco.

---

## Phase 6: Polish e Validação

**Purpose**: Remover código morto remanescente do shell antigo e validar o resultado final no browser.

- [x] T013 Remover de `dashboard/gui/active_consents.html` todo CSS e HTML não utilizado após a migração: classes `.filter-bar`, `.filter-group`, `.btn-apply`, `.page`, `.page-header`, `.card` (substituída por `.chart-card`), `.card-header` (substituída por `.chart-head`), `.card-title`/`.card-subtitle` (substituídas), `.toggle-group`, variáveis `--radius-sm/md/lg`, `--font-mono`; verificar que nenhuma referência JS a esses IDs/classes permanece; confirmar que o arquivo compila sem warnings no browser console

- [ ] T014 Executar validação manual no browser (Constituição II) em `dashboard/gui/active_consents.html` via `uvicorn server:app --port 8000`: (1) página carrega sem erros no console; (2) titlebar com logo "OF", nome, 3 tabs (Ativos ativo), theme toggle visível; (3) sidebar exibe lista de receptores com dots coloridos; (4) search na sidebar filtra a lista; (5) clicar em receptor recarrega todos os 4 gráficos; (6) quick-range "3m" atualiza período e recarrega; (7) theme toggle alterna dark/light e persiste após F5; (8) loading sweep visível em todos os cards ao recarregar; (9) navegação para Ecossistema e volta → filtros preservados; (10) status bar mostra data de referência

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 e T002 independentes entre si → ambos DEVEM ser concluídos antes de T003
- **Foundational (Phase 2)**: T003 → T004 (T004 popula o HTML criado por T003); ambos bloqueiam as phases de US
- **US1+US2 (Phase 3)**: T005 e T006 independentes (JS sidebar vs JS theme); T007 independente (CSS/HTML); T008 depende de T007 (JS do date bar usa os elementos criados por T007)
- **US3 (Phase 4)**: T009 e T010 dependem de Phase 2 e Phase 3 (para conhecer os IDs dos cards)
- **US4+US5 (Phase 5)**: T011 e T012 independentes entre si; ambos dependem de T008
- **Polish (Phase 6)**: T013 → T014 (validação só após limpeza)

### User Story Dependencies

- **US1 (P1)**: Depende de Foundational; independente de US2
- **US2 (P1)**: Depende de Foundational; independente de US1 (mas ambos concluem o MVP juntos)
- **US3 (P1)**: Depende de US1+US2 (precisa dos card IDs criados na migração)
- **US4 (P2)**: Depende de US2 (precisa do `refresh()` já existente)
- **US5 (P2)**: Depende de US2 (precisa do date bar para ler o status bar)

### Parallel Opportunities

```bash
# Phase 1 — em paralelo:
T001: tokens + body CSS
T002: shell classes CSS (titlebar, app-body, main-content)

# Phase 3 — alguns em paralelo:
T005: JS sidebar
T006: JS theme toggle (independente do T005)
T007: CSS + HTML date-bar (independente de T005 e T006)
# T008 aguarda T007

# Phase 5 — em paralelo:
T011: sessionStorage JS
T012: CSS + HTML status-bar
```

---

## Implementation Strategy

### MVP (US1 + US2 — Phases 1–3)

1. Phase 1: T001 + T002 (paralelo)
2. Phase 2: T003 → T004
3. Phase 3: T005 + T006 + T007 (paralelo) → T008
4. **PARAR e VALIDAR**: Shell completo funcional. Sidebar interativa. Date bar com quick-range. Theme toggle. Todos os 4 gráficos respondem a filtros.

### Entrega Completa

5. Phase 4: T009 → T010 (loading states)
6. Phase 5: T011 + T012 (paralelo — sessionStorage + status bar)
7. Phase 6: T013 → T014 (limpeza + validação final)

---

## Notes

- **Arquivo único**: todas as tasks operam em `dashboard/gui/active_consents.html` — não há paralelismo de arquivo, apenas de seções lógicas
- **Zero alterações de backend**: nenhum arquivo Python é modificado nesta feature
- **Constituição VI**: cada task implementa diretamente um componente do Shell Contract ratificado em v1.1.0
- **Validação manual obrigatória**: T014 é mandatório por Constituição II (frontend UI change)
- **IDs de card sugeridos**: `card-evolution`, `card-matrix`, `card-ranking`, `card-intensity` — devem ser consistentes entre T009, T010 e T012
