# Tasks: Visual Parity — Matriz Receptor × Transmissor

**Feature**: 005-matrix-visual-parity | **File**: `dashboard/gui/active_consents.html`

## Phase 1 — Setup CSS base

- [x] T001 Alterar `#matrix-table` de `border-collapse:collapse` para `border-collapse:separate; border-spacing:3px` no `<style>` de `dashboard/gui/active_consents.html`

## Phase 2 — Visual parity das células (US1)

- [x] T002 [US1] Atualizar CSS `#matrix-table td` — remover `font-family: "JetBrains Mono"`, remover `border: 1px solid`, adicionar `border-radius:var(--r-sm)`, ajustar padding/size/weight para `7px 4px / 11px / 500`, mudar hover de `filter:brightness` para `opacity:0.82; transform:scale(1.03)` em `dashboard/gui/active_consents.html`
- [x] T003 [US1] Atualizar `heatColor()` — substituir gradiente dark pelo gradiente pastel-azul de `dashboard.html` (`199,228,250` → `13,79,139`) e retornar `{css, brightness}` em `dashboard/gui/active_consents.html`
- [x] T004 [US1] Atualizar `renderMatrix()` — usar `col.css`/`col.brightness` da nova `heatColor`, tratar `v===0` com `background:var(--bg-elevated)` e `—`, atualizar cor de texto das células não-zero em `dashboard/gui/active_consents.html`

## Phase 3 — Brand colors e tipografia de cabeçalhos (US2)

- [x] T005 [US2] Atualizar CSS `#matrix-table th[data-col-idx]` — `color:var(--text-muted)`, `font-weight:500`, `vertical-align:bottom` em `dashboard/gui/active_consents.html`
- [x] T006 [US2] Atualizar CSS `#matrix-table td.row-label` — remover `font-weight:600` da regra base, adicionar `hover {color:var(--text-accent)}`, ajustar `font-size` para `var(--tx-sm)` em `dashboard/gui/active_consents.html`
- [x] T007 [US2] Atualizar `renderMatrix()` — adicionar ponto colorido (`7px circle`) antes do nome do receptor quando `_allReceptors.find(r=>r.label===rec)?.color` existir em `dashboard/gui/active_consents.html`

## Phase 4 — Validação manual (Constituição II)

- [ ] T008 Executar validação manual no browser (Constituição II — Frontend) conforme 10 cenários em `specs/005-matrix-visual-parity/quickstart.md`: células arredondadas, hover scale/opacity, zeros com —, paleta pastel, fonte proporcional, pontos de cor nos receptores, tipografia de transmissores, retrocompatibilidade com feature 004, temas claro/escuro, sem erros de console

## Dependencies

```
T001 → T002
T003 → T004
T002 → T004
T001 → T003
T004 → T007
T005 → T008
T006 → T007
T007 → T008
T004 → T008
```

## Parallel Execution

```
T002 ‖ T003   (T002 é CSS, T003 é JS — mesma regra de arquivo mas conteúdo independente)
T005 ‖ T006   (CSS edits independentes no mesmo arquivo)
```

## Implementation Order

```
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008
```
