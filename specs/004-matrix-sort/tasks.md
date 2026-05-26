# Tasks: Ordenação Interativa da Matriz Receptor × Transmissor

**Feature**: 004-matrix-sort | **File**: `dashboard/gui/active_consents.html`

## Phase 1 — Setup (estado global + CSS + HTML)

- [ ] T001 Adicionar variáveis de estado `_matrixData` e `_matrixSort` no escopo global de `dashboard/gui/active_consents.html`
- [ ] T002 Adicionar regras CSS para cursores e `.sort-active` no `<style>` de `dashboard/gui/active_consents.html`
- [ ] T003 Alterar o HTML do `.chart-head` do `card-matrix` para incluir o botão `#btn-matrix-reset` em `dashboard/gui/active_consents.html`

## Phase 2 — Helpers de sort (US1)

- [ ] T004 [P] [US1] Implementar `_sortedPerm(totals, labels)` — retorna array de índices por totals desc + alfa em `dashboard/gui/active_consents.html`
- [ ] T005 [P] [US1] Implementar `_rowTotal(i)` e `_colTotal(j)` — soma de linha/coluna nos dados brutos em `dashboard/gui/active_consents.html`

## Phase 3 — Renderização desacoplada (US1)

- [ ] T006 [US1] Implementar `renderMatrix(rowPerm, colPerm)` — extrai e refatora a lógica de render da tabela atual; adiciona `data-row-idx`/`data-col-idx` nos `<th>`; aplica `.sort-active` baseado em `_matrixSort` em `dashboard/gui/active_consents.html`
- [ ] T007 [US1] Implementar `_applyMatrixSort()` — calcula permutações via `_matrixSort`, chama `renderMatrix`, controla visibilidade do `#btn-matrix-reset` em `dashboard/gui/active_consents.html`
- [ ] T008 [US1] Refatorar `loadMatrix()` — mantém fetch + `setCardLoading`; ao receber dados: `_matrixData = data; _matrixSort = null; _applyMatrixSort()` em `dashboard/gui/active_consents.html`

## Phase 4 — Interatividade por clique (US2 + US3)

- [ ] T009 [US2] Implementar `_setMatrixSort(sort)` — atualiza `_matrixSort` e chama `_applyMatrixSort()` em `dashboard/gui/active_consents.html`
- [ ] T010 [US2] Adicionar event delegation no `#matrix-container` para cliques em `<th[data-row-idx]>` (reordena colunas) em `dashboard/gui/active_consents.html`
- [ ] T011 [US3] Adicionar event delegation no `#matrix-container` para cliques em `<th[data-col-idx]>` (reordena linhas) em `dashboard/gui/active_consents.html`

## Phase 5 — Reset (US4)

- [ ] T012 [US4] Adicionar listener no `#btn-matrix-reset` → `_setMatrixSort(null)` em `dashboard/gui/active_consents.html`

## Phase 6 — Validação manual (Constituição II)

- [ ] T013 Executar validação manual no browser (Constituição II — Frontend) conforme cenários em `specs/004-matrix-sort/quickstart.md`: ordenação padrão ao carregar, reordenar por clique em receptor, reordenar por clique em transmissor, redefinir, filtro redefine automaticamente, sem erros no console

## Dependencies

```
T001 → T004, T005, T006, T007, T008, T009
T004, T005 → T006
T006 → T007
T007 → T008
T008 → T010, T011
T009 → T010, T011
T010, T011 → T012
T002, T003 → T007 (CSS e HTML devem existir antes de applyMatrixSort referenciar #btn-matrix-reset)
T012 → T013
```

## Parallel Execution

```
T004 ‖ T005   (helpers independentes)
T010 ‖ T011   (event delegations independentes)
T001 ‖ T002 ‖ T003   (setup independente entre si)
```
