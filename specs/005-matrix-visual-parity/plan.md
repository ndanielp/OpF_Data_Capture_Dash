# Implementation Plan: Visual Parity — Matriz Receptor × Transmissor

**Branch**: `006-matrix-visual-parity` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)

## Summary

Refatorar o visual do card "Matriz Receptor × Transmissor" em `dashboard/gui/active_consents.html` para igualar o estilo do heatmap "Intensidade de Uso das APIs" em `dashboard/gui/dashboard.html`. As mudanças são: células arredondadas com espaçamento, nova paleta de calor, hover com scale/opacity, células zero com `—`, fonte proporcional, ponto de cor nos receptores, e tipografia alinhada nos cabeçalhos de transmissores. Sem mudanças de backend ou novos endpoints.

## Technical Context

| Item | Decisão |
|---|---|
| Arquivo alvo | `dashboard/gui/active_consents.html` (única mudança) |
| Backend | Sem alterações |
| Brand colors | `_allReceptors` já carregado via `loadReceptors()` — sem nova API |
| Dependências novas | Nenhuma |
| Feature base | Feature 004 (sort interativo) deve permanecer intacta |

## Constitution Check

| Princípio | Status | Justificativa |
|---|---|---|
| I — Simplicidade | ✓ | Sem nova abstração: lookup de cor inline; `heatColor` refatorada in-place; helper `_recColor` evitado (1 call site) |
| II — Testes | ✓ | UI change → validação manual no browser (Constituição II — Frontend); quickstart.md define 10 cenários |
| III — UX Consistency | ✓ | Cores das células via paleta de calor existente; brand colors via `_allReceptors` (API_GROUPS-aligned); sem hardcode de hex |
| IV — Performance | ✓ | Sem nova query; re-render é in-memory O(n²) como antes; nenhuma chamada de rede adicional |
| V — Paradigma | ✓ | Vanilla JS; single file; sem novos endpoints; sem mudança de schema |
| VI — UI Shell Contract | ✓ | Sem alteração do shell; mudanças restritas ao conteúdo do `.chart-card` |

## File Structure

```
dashboard/gui/active_consents.html    ← único arquivo modificado
specs/005-matrix-visual-parity/
├── plan.md
├── research.md
├── quickstart.md
└── tasks.md
```

## Architecture Decisions

### A1 — CSS: border-collapse → separate + border-spacing

```css
/* ANTES */
#matrix-table { border-collapse: collapse; }

/* DEPOIS */
#matrix-table { border-collapse: separate; border-spacing: 3px; }
```

Células `<td>` de dados ganham `border-radius: var(--r-sm)`. Borda `1px solid var(--border-subtle)` removida de `td` (substituída pelo gap visual do border-spacing). Cabeçalhos `<th>` mantêm bordas (para o fundo `var(--bg-elevated)` funcionar como header visual).

### A2 — heatColor() alinhada com dashboard.html

```js
// ANTES (string simples, gradiente dark)
function heatColor(value, maxValue) {
  if (!value || !maxValue) return 'transparent';
  const ratio = Math.min(value / maxValue, 1);
  const r = Math.round(19  + (0  - 19)  * ratio);
  const g = Math.round(21  + (82 - 21)  * ratio);
  const b = Math.round(30  + (255 - 30) * ratio);
  return `rgb(${r},${g},${b})`;
}

// DEPOIS (objeto {css, brightness}, gradiente pastel→médio como dashboard.html)
function heatColor(val, maxVal) {
  const ratio = Math.min(val / (maxVal || 1), 1);
  const r = Math.round(199 + (13  - 199) * ratio);
  const g = Math.round(228 + (79  - 228) * ratio);
  const b = Math.round(250 + (139 - 250) * ratio);
  return { css: `rgb(${r},${g},${b})`, brightness: (r * 299 + g * 587 + b * 114) / 1000 };
}
```

`renderMatrix()` atualizado para usar `col.css` e `col.brightness > 145 ? '#13151E' : '#EEF0F6'`.

### A3 — Células zero com `—`

Em `renderMatrix()`, célula com `v === 0` recebe inline style com `background: var(--bg-elevated)` e text `—` com cor `var(--text-muted)`. Sem aplicar `heatColor`.

```js
// Dentro do forEach de colPerm:
if (v === 0) {
  row += `<td style="background:var(--bg-elevated);color:var(--text-muted)"
              data-rec="${rec}" data-txm="${transmitters[j]}" data-val="0"
              onmouseenter="showTip(event)" onmouseleave="hideTip()">—</td>`;
} else {
  const col = heatColor(v, max_value);
  const fg  = col.brightness > 145 ? '#13151E' : '#EEF0F6';
  row += `<td style="background:${col.css};color:${fg}"
              data-rec="${rec}" data-txm="${transmitters[j]}" data-val="${v}"
              onmouseenter="showTip(event)" onmouseleave="hideTip()">${_fmt(v)}</td>`;
}
```

### A4 — CSS das células de dados: font + hover

```css
/* ANTES */
#matrix-table td {
  border: 1px solid var(--border-subtle);
  padding: var(--s1) var(--s2);
  text-align: center; cursor: default;
  min-width: 52px;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 10px; transition: filter 0.1s;
}
#matrix-table td:hover { filter: brightness(1.3); }

/* DEPOIS */
#matrix-table td {
  border-radius: var(--r-sm);
  padding: 7px 4px;
  text-align: center; cursor: default;
  min-width: 52px;
  font-family: inherit;
  font-size: 11px; font-weight: 500;
  transition: opacity 0.15s, transform 0.1s;
  vertical-align: middle;
}
#matrix-table td:hover:not(.row-label) { opacity: 0.82; transform: scale(1.03); }
```

### A5 — CSS de cabeçalhos de transmissores (th[data-col-idx])

```css
/* Alinhar com .heatmap-th */
#matrix-table th[data-col-idx] {
  color: var(--text-muted);     /* era var(--text-secondary) */
  font-weight: 500;
  vertical-align: bottom;
  font-size: var(--tx-xs);
}
```

### A6 — Ponto de cor nos receptores (row-label)

Em `renderMatrix()`, dentro do `rowPerm.forEach`, o `<td class="row-label">` recebe um ponto colorido quando o receptor tem cor em `_allReceptors`:

```js
const color = _allReceptors.find(r => r.label === rec)?.color || null;
const dot   = color
  ? `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${color};margin-right:5px;vertical-align:middle;flex-shrink:0"></span>`
  : '';
const recShort = rec.length > 20 ? rec.slice(0, 20) + '…' : rec;
let row = `<tr><td class="row-label" title="${rec}" data-row-idx="${i}" style="cursor:pointer${isActive ? ';font-weight:700;text-decoration:underline dotted;color:var(--text-accent)' : ''}">${dot}${recShort}</td>`;
```

### A7 — CSS do row-label

```css
/* ANTES */
#matrix-table td.row-label {
  background: var(--bg-elevated);
  color: var(--text-secondary); font-weight: 600;
  text-align: left; padding: var(--s2) var(--s3);
  position: sticky; left: 0; z-index: 1;
  font-family: inherit; font-size: var(--tx-xs);
  max-width: 200px; overflow: hidden; text-overflow: ellipsis;
}

/* DEPOIS — alinhado com .heatmap-row-label */
#matrix-table td.row-label {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  text-align: left; padding: var(--s2) var(--s3);
  position: sticky; left: 0; z-index: 1;
  font-family: inherit; font-size: var(--tx-sm);
  max-width: 200px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
#matrix-table td.row-label:hover { color: var(--text-accent); }
```

Remover `font-weight: 600` da regra base (fica 700 apenas quando `sort-active`).

### A8 — Remover borda de td.row-label

Com `border-collapse: separate`, o `td.row-label` (sticky) não deve ter borda que conflite. Remover `border: 1px solid var(--border-subtle)` do `.row-label` e das células de dados.

## Implementation Order

1. **CSS A1/A4/A5/A7/A8**: todas as mudanças de CSS (border-collapse, cells, th headers, row-label)
2. **A2 `heatColor()`**: atualizar função para retornar `{css, brightness}`
3. **A3 + A4 `renderMatrix()`**: atualizar lógica de renderização de células (zero check, heatColor usage, font)
4. **A6 `renderMatrix()`**: adicionar ponto de cor nos receptores
5. **Validação manual**: 10 cenários do quickstart.md
