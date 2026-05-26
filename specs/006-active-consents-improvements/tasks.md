# Tasks: Melhorias no Dashboard de Consentimentos Ativos

**Feature**: 006-active-consents-improvements | **Files**: `dashboard/gui/active_consents.html`, `dashboard/gui/dashboard.html`, `dashboard/gui/receptor_profile.html`

---

## Phase 1 — Fundação Compartilhada

**Purpose**: Helper function usada por US1 (tornado) e US2 (matriz) — deve existir antes das implementações.

- [x] T001 Adicionar função `_fmtShort(n)` em `dashboard/gui/active_consents.html` logo após `_fmt()` (linha ~729): retorna `n >= 1e6` → `"X,XX M"`, `n >= 1e3` → `"X,XX k"` com vírgula pt-BR, `n < 1e3` → `n.toLocaleString('pt-BR')`

---

## Phase 2 — User Story 1: Gráfico Tornado + Layout Responsivo (Priority: P1) 🎯 MVP

**Goal**: Exibir tornado de top receptores × transmissores lado a lado com a evolução temporal.

**Independent Test**: Abrir `http://localhost:8000/active-consents`, verificar card tornado com barras simétricas lado a lado com evolução em viewport ≥ 900 px; empilhado em < 900 px.

- [x] T002 [P] [US1] Adicionar bloco de CSS `.tornado-row`, `.tornado-name`, `.tornado-left-bar`, `.tornado-right-bar`, `.t-bar`, `.t-bar-left`, `.t-bar-right`, `.tornado-value`, `.tornado-value-left`, `.tornado-value-right`, `.tornado-missing`, `#tornado-active-container`, `.tornado-header`, `.tornado-header-left`, `.tornado-header-center`, `.tornado-header-right` na seção `<style>` de `dashboard/gui/active_consents.html` (baseado nos estilos de `receptor_profile.html`, substituindo `#tornadoContainer` por `#tornado-active-container`)
- [x] T003 [P] [US1] Adicionar função `renderTornado(recItems, txmItems)` em `dashboard/gui/active_consents.html` (antes de `renderMatrix()`): ordenar recItems por total desc+alfa, construir txmMap, calcular scaleMax e barW, gerar HTML com `.tornado-row` para cada instituição usando `_fmtShort()` para valores e `title` para tooltip
- [x] T004 [P] [US1] Envolver o card de evolução `<div class="chart-card" id="card-evolution">` em `dashboard/gui/active_consents.html` num `<div class="two-col" id="row-evo-tornado">` e adicionar após ele o novo card `<div class="chart-card" id="card-tornado-active">` com `.chart-head` (título "Tornado — Top Receptores × Transmissores", subtitle id="tornado-active-subtitle"), `.tornado-header` (← Receptores / Instituição / Transmissores →) e `<div id="tornado-active-container"></div>`
- [x] T005 [US1] Atualizar `loadRanking()` em `dashboard/gui/active_consents.html`: adicionar `setCardLoading('card-tornado-active', true)` no início, extrair `recItems` e `txmItems` dos resultados já buscados pelo `Promise.allSettled`, chamar `renderTornado(recItems, txmItems)` e `setCardLoading('card-tornado-active', false)` ao final

**Checkpoint**: Tornado visível com dados, layout responsivo funcionando.

---

## Phase 3 — User Story 2: Totais na Matriz + Números Abreviados (Priority: P2)

**Goal**: Primeira linha e primeira coluna da matriz exibem totais; todos os valores usam formato abreviado.

**Independent Test**: Carregar matriz, verificar linha "Total" no topo com soma por transmissor, coluna "Total" após label de receptor com soma por linha, e valor 1514 exibido como "1,51 k".

- [x] T006 [US2] Em `dashboard/gui/active_consents.html`, substituir `_fmt(v)` por `_fmtShort(v)` nas células de dados da matriz dentro de `renderMatrix()` (linha da chamada `_fmt(v)` na cell não-zero) e substituir `_fmt(Number(td.dataset.val))` por `_fmtShort(Number(td.dataset.val))` no tooltip `showTip()`
- [x] T007 [US2] Em `renderMatrix()` de `dashboard/gui/active_consents.html`: (1) antes do thead, calcular `const colTotals = transmitters.map((_, j) => receptors.reduce((s, _, i) => s + (values[i][j] || 0), 0))` e `const grandTotal = colTotals.reduce((s, v) => s + v, 0)`; (2) no thead, adicionar `<th class="row-header" style="min-width:52px">Total</th>` como segunda coluna (após `row-header`, antes das colunas de transmissores via `colPerm`); (3) no início de tbody (antes de `rowPerm.forEach`), inserir linha de totais: `<tr><td class="row-label" style="font-weight:600">Total</td>` + célula de grand total + células `colTotals[j]` para cada `j` em `colPerm`, usando `_fmtShort()` para valores > 0 e `—` para 0
- [x] T008 [US2] Em `renderMatrix()` de `dashboard/gui/active_consents.html`: (1) calcular `const rowTotals = receptors.map((_, i) => transmitters.reduce((s, _, j) => s + (values[i][j] || 0), 0))`; (2) em cada linha de receptor no `rowPerm.forEach`, inserir APÓS `<td class="row-label">` e ANTES do `colPerm.forEach` uma célula `<td style="background:var(--bg-elevated);color:var(--text-secondary);font-weight:600">` exibindo `_fmtShort(rowTotals[i])` (ou `—` se zero)

**Checkpoint**: Linha e coluna de totais visíveis, números abreviados em todas as células da matriz, sort (feature 004) preservado com totais fixados.

---

## Phase 4 — User Story 3: Renomeações e Reordenação de Navegação (Priority: P3)

**Goal**: Abas na ordem correta com nomes corretos em todos os arquivos; título do gráfico corrigido no Ecossistema.

**Independent Test**: Abrir as 3 URLs e verificar abas em ordem Ecossistema → Consentimentos Ativos → Perfil Receptor; verificar título "Evolução Consentimentos Únicos" em `/`.

- [x] T009 [P] [US3] Em `dashboard/gui/active_consents.html`: (1) alterar `<title>Ativos …` para `<title>Consentimentos Ativos — Open Finance Brasil</title>`; (2) reordenar nav tabs para: `Ecossistema` (href="/") → `Consentimentos Ativos` (href="/active-consents", estilo ativo) → `Perfil Receptor` (href="/profile")
- [x] T010 [P] [US3] Em `dashboard/gui/dashboard.html`: (1) reordenar nav tabs para: `Ecossistema` (ativo) → `Consentimentos Ativos` (href="/active-consents") → `Perfil Receptor` (href="/profile"); (2) alterar `<div class="chart-title">Evolução Consentimentos</div>` para `<div class="chart-title">Evolução Consentimentos Únicos</div>`
- [x] T011 [P] [US3] Em `dashboard/gui/receptor_profile.html`: reordenar nav tabs para: `Ecossistema` (href="/") → `Consentimentos Ativos` (href="/active-consents") → `Perfil Receptor` (href="/profile", estilo ativo); renomear "Perfil Receptores" para "Perfil Receptor" no texto do link ativo

**Checkpoint**: Navegação consistente nas 3 páginas, título do gráfico atualizado.

---

## Phase 5 — Validação Manual

- [ ] T012 Executar validação manual no browser conforme `specs/006-active-consents-improvements/quickstart.md`: 14 cenários cobrindo tornado, layout responsivo, tooltips, totais da matriz, números abreviados, tabs, rename de gráfico, retrocompat features 004+005

---

## Dependencies

```
T001 → T003   (renderTornado usa _fmtShort)
T001 → T006   (células da matriz usam _fmtShort)
T001 → T007   (células de total usam _fmtShort)
T002 → T005   (CSS deve existir antes de renderTornado ser invocado)
T003 → T005   (função deve existir antes de ser chamada em loadRanking)
T004 → T005   (card-tornado-active deve existir no DOM)
T007 → T008   (rowTotals pode ser calculado separado mas ordem de modificação em renderMatrix evita conflito)
T005 → T012
T008 → T012
T009 → T012
T010 → T012
T011 → T012
```

## Parallel Execution

```
T002 ‖ T003 ‖ T004   (CSS, JS function, HTML — conteúdo disjunto no mesmo arquivo)
T009 ‖ T010 ‖ T011   (edits em arquivos distintos ou seções distintas)
T006 pode ser feito antes de T007/T008 (mesma função, subseção diferente)
```

## Implementation Order

```
T001 → (T002 ‖ T003 ‖ T004) → T005 → T006 → T007 → T008 → (T009 ‖ T010 ‖ T011) → T012
```

## Implementation Strategy

### MVP (US1 apenas)
1. T001 — `_fmtShort()`
2. T002, T003, T004 em paralelo — CSS + função + HTML
3. T005 — integração em loadRanking()
4. **STOP e VALIDAR**: cenários 1–5 do quickstart

### Entrega completa
1. MVP + T006, T007, T008 — totais e abreviação da matriz
2. T009, T010, T011 em paralelo — renomeações
3. T012 — validação completa dos 14 cenários
