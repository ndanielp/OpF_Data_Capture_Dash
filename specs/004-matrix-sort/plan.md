# Implementation Plan: Ordenação Interativa da Matriz Receptor × Transmissor

**Branch**: `004-matrix-sort` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)

## Summary

Refatorar `loadMatrix()` em `dashboard/gui/active_consents.html` para ordenar automaticamente receptores (linhas) por volume total decrescente e transmissores (colunas) por volume total decrescente ao renderizar, e permitir reordenação interativa clicando nos cabeçalhos da tabela. Um botão "Redefinir" no cabeçalho do card restaura a ordem padrão. Todos os dados já estão no cliente após o fetch existente — zero mudanças de backend.

## Technical Context

| Item | Decisão |
|---|---|
| Arquivo alvo | `dashboard/gui/active_consents.html` (única mudança) |
| Backend | Sem alterações — endpoint `/api/active-consents/matrix` permanece idêntico |
| Estratégia | Separar dados brutos (`_matrixData`) de renderização (`renderMatrix`) + sort client-side |
| Dependências novas | Nenhuma |
| DB / API | Sem mudanças |

## Constitution Check

| Princípio | Status | Justificativa |
|---|---|---|
| I — Simplicidade | ✓ | Refatoração local; sem nova abstração externa; helpers com ≥2 call sites internos |
| II — Testes | ✓ | UI change → validação manual no browser (Constituição II — Frontend) |
| III — UX Consistency | ✓ | Sem alteração de cores, filtros ou shell; botão Redefinir usa classe `.quick-btn` existente |
| IV — Performance | ✓ | Sort é O(n log n) client-side sobre dados já carregados; sem nova query |
| V — Paradigma | ✓ | Vanilla JS; sem framework; sem novos endpoints; sem mudança de schema |
| VI — UI Shell Contract | ✓ | Não altera shell; botão Redefinir adicionado ao `.chart-head` existente |

## File Structure

```
dashboard/gui/active_consents.html    ← único arquivo modificado
specs/004-matrix-sort/
├── plan.md
├── quickstart.md
└── tasks.md
```

Nenhum arquivo Python é alterado. Nenhuma rota nova.

## Architecture Decisions

### A1 — Separação estado × renderização

Atualmente `loadMatrix()` busca dados e renderiza inline. Após a refatoração:

```
_matrixData = { receptors[], transmitters[], values[][], max_value, reference_date }
              ← guardado em módulo-level ao receber resposta da API

renderMatrix(rowPerm, colPerm)
              ← função pura de renderização; recebe arrays de índices (permutações)
```

`_matrixData` é `null` enquanto não há dados carregados.

### A2 — Estado do critério de ordenação ativo

```js
// null → ordenação padrão (totais)
// { axis: 'row', index: i } → receptor original[i] clicado → colunas ordenadas por row i
// { axis: 'col', index: j } → transmissor original[j] clicado → linhas ordenadas por col j
let _matrixSort = null;
```

O índice guardado referencia os arrays originais de `_matrixData` (invariante a reordenações anteriores).

### A3 — Funções de permutação (sort)

```js
// Retorna array de índices ordenado por totals[i] desc; empate: alfabético por labels[i]
function _sortedPerm(totals, labels) { ... }

// Soma de uma linha i sobre todas as colunas
function _rowTotal(i)  { return _matrixData.transmitters.reduce((s,_,j) => s + _matrixData.values[i][j], 0); }

// Soma de uma coluna j sobre todas as linhas
function _colTotal(j)  { return _matrixData.receptors.reduce((s,_,i) => s + _matrixData.values[i][j], 0); }
```

`_applyMatrixSort()` usa essas funções para calcular as duas permutações (linhas e colunas) e passa para `renderMatrix`.

### A4 — Event delegation no `<table>`

Em vez de `onclick` inline em cada `<th>`, usa-se um único listener no elemento `<table>`:

```js
table.addEventListener('click', e => {
  const th = e.target.closest('th');
  if (!th || !_matrixData) return;
  const ci = th.dataset.colIdx, ri = th.dataset.rowIdx;
  if (ci !== undefined) _setMatrixSort({ axis: 'col', index: +ci });
  else if (ri !== undefined) _setMatrixSort({ axis: 'row', index: +ri });
});
```

Os `<th>` recebem `data-col-idx` ou `data-row-idx` com o índice no array original de `_matrixData`.

### A5 — Destaque visual do critério ativo

- `<th>` clicado recebe classe `.sort-active` → `font-weight:700; text-decoration:underline dotted`
- Todos os `<th>` clicáveis recebem `cursor:pointer` via seletor CSS `[data-col-idx], [data-row-idx]`
- `renderMatrix` recalcula qual `<th>` é `.sort-active` com base em `_matrixSort`
- Indicador de ordenação acessível: estilo não depende apenas de cor (usa sublinhado + negrito)

### A6 — Botão "↺ Redefinir"

Adicionado ao `.chart-head` do `card-matrix`, à direita do bloco título/subtítulo:

```html
<div class="chart-head" style="justify-content:space-between; align-items:flex-start">
  <div>
    <div class="chart-title">Matriz Receptor × Transmissor</div>
    <div class="chart-subtitle" id="matrix-refdate">...</div>
  </div>
  <button id="btn-matrix-reset" class="quick-btn" style="display:none; font-size:var(--tx-sm)">
    ↺ Redefinir
  </button>
</div>
```

- `display:none` quando `_matrixSort === null` (sem ação necessária)
- `display:inline-flex` quando uma ordenação por clique está ativa
- Clique: `_setMatrixSort(null)` → restaura padrão

### A7 — Integração com `loadMatrix()`

`loadMatrix()` permanece responsável pelo fetch e `setCardLoading`. Após receber dados:
1. Grava em `_matrixData`
2. Redefine `_matrixSort = null` (garante FR-010 — novo filtro → ordem padrão)
3. Chama `_applyMatrixSort()`

`_setMatrixSort(sort)` atualiza `_matrixSort` e chama `_applyMatrixSort()`.

`_applyMatrixSort()` calcula permutações, chama `renderMatrix(rowPerm, colPerm)`, mostra/oculta botão Redefinir.

### A8 — CSS adicional (mínimo)

```css
#matrix-table th[data-col-idx],
#matrix-table th[data-row-idx]  { cursor: pointer; }
#matrix-table th.sort-active    { font-weight: 700; text-decoration: underline dotted; }
#matrix-table th[data-col-idx]:hover,
#matrix-table th[data-row-idx]:hover { background: var(--bg-hover); }
```

## Implementation Order

1. **Estado global**: `let _matrixData = null; let _matrixSort = null;`
2. **CSS A8**: 4 regras novas no `<style>`
3. **HTML A6**: adicionar `#btn-matrix-reset` ao `.chart-head` do `card-matrix`
4. **`_sortedPerm(totals, labels)`**: helper genérico, desc+alfa
5. **`_rowTotal(i)` / `_colTotal(j)`**: helpers de soma
6. **`renderMatrix(rowPerm, colPerm)`**: extrai lógica de render da tabela atual; usa permutações; aplica `.sort-active` baseado em `_matrixSort`
7. **`_applyMatrixSort()`**: calcula permutações, chama `renderMatrix`, controla visibilidade do botão reset
8. **`_setMatrixSort(sort)`**: atualiza `_matrixSort`, chama `_applyMatrixSort()`
9. **Event delegation**: listener no `table` (após `renderMatrix` para garantir que `table` existe — usar delegação no `#matrix-container`)
10. **`loadMatrix()`**: simplificar — mantém fetch + `setCardLoading`; ao receber dados: `_matrixData = data; _matrixSort = null; _applyMatrixSort()`
11. **`#btn-matrix-reset`**: listener → `_setMatrixSort(null)`
12. **Validação manual no browser**
