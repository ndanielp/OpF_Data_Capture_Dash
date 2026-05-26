# Research: Visual Parity — Matriz Receptor × Transmissor

**Feature**: 005-matrix-visual-parity | **Date**: 2026-05-26

## Decisões Técnicas

### D1 — Fonte dos brand colors dos receptores

**Decisão**: Usar `_allReceptors` (já carregado em `active_consents.html` via `loadReceptors()`) sem nova chamada de API.

**Rationale**: `_allReceptors = [{label, color, top, uuid}]` está populado desde o boot da página. O mesmo padrão é usado no heatmap do Ecossistema com `function recColor(rec)` que faz lookup em `_allReceptors`. Não é necessário buscar `/api/of/brand-colors` separadamente.

**Alternativas consideradas**:
- Fetch `/api/of/brand-colors` no `loadMatrix()` — rejeitado: latência extra e dado já disponível.
- Hardcodear cores — rejeitado: viola Princípio III (cores devem vir de fonte central).

### D2 — Brand colors para transmissores

**Decisão**: Transmissores recebem apenas paridade tipográfica (cor muted, tamanho, peso); sem indicador de cor por instituição.

**Rationale**: No heatmap do Ecossistema, as colunas representam _grupos de APIs_ (Conta, Cartão, etc.) com cores de grupo — não instituições individuais. Na matriz, transmissores são instituições individuais e não têm mapeamento de cor centralizado disponível sem nova API. FR-007 especifica apenas "estilo tipográfico equivalente", não indicador de cor.

**Alternativas consideradas**:
- Buscar `/api/of/brand-colors` para transmissores também — rejeitado: escopo além do especificado; pode ser adicionado em feature futura.

### D3 — Inlining vs. função auxiliar para cor de receptor

**Decisão**: Inline do lookup de cor diretamente em `renderMatrix()` — sem nova função nomeada `_recColor`.

**Rationale**: Princípio I — nova abstração requer ≥3 call sites. O lookup tem apenas 1 call site em `renderMatrix`. Inlining é simples: `_allReceptors.find(r => r.label === rec)?.color || null`.

### D4 — Paleta de calor (heatColor)

**Decisão**: Substituir `heatColor()` de `active_consents.html` pela mesma implementação do `dashboard.html`:
- Gradiente: `rgb(199,228,250)` (baixo) → `rgb(13,79,139)` (alto)
- Retorno: `{css, brightness}` (permite determinar cor de texto via limiar `brightness > 145`)

**Rationale**: O gradiente atual da matriz (`rgb(19,21,30)` near-black → `rgb(0,82,255)` bright blue) é visualmente muito diferente do heatmap. A versão do dashboard usa tons mais pastel e legíveis — é a paleta de referência.

**Alternativas consideradas**:
- Unificar numa função compartilhada — rejeitado: sem mecanismo de JS compartilhado entre páginas sem bundler; duplicate é o padrão do projeto.

### D5 — CSS de células: border-collapse vs border-spacing

**Decisão**: Mudar `#matrix-table` para `border-collapse: separate; border-spacing: 3px`. Remover `border: 1px solid var(--border-subtle)` das células de dados (o espaçamento cria a separação visual). Manter borda apenas em `th` e `td.row-label`.

**Rationale**: O heatmap usa exatamente `border-collapse: separate; border-spacing: 3px`. Células de dados ganham `border-radius: var(--r-sm)` que só funciona com `border-collapse: separate`.

### D6 — Hover em células

**Decisão**: Substituir `filter: brightness(1.3)` por `opacity: 0.82; transform: scale(1.03)` com `transition: opacity 0.15s, transform 0.1s`.

**Rationale**: Matching exato do `.heatmap-cell:hover` em `dashboard.html`.

### D7 — Células zero

**Decisão**: Células com `v === 0` recebem `background: var(--bg-elevated)` e exibem `—` com cor `var(--text-muted)`, independentemente de `max_value`.

**Rationale**: Matching do `.heatmap-cell.empty` — sem escala de calor em zeros.

### D8 — Fonte das células

**Decisão**: Remover `font-family: "JetBrains Mono", "Fira Code", monospace` das `td` de dados. Usar `font-family: inherit`. Ajustar para `font-size: 11px; font-weight: 500` (matching `heatmap-cell`).

### D9 — Tipografia dos cabeçalhos de transmissores

**Decisão**: Alinhar `#matrix-table th[data-col-idx]` com `.heatmap-th`:
- `color: var(--text-muted)` (atual: `var(--text-secondary)`)
- `font-weight: 500`
- `vertical-align: bottom`
- Manter `font-size: var(--tx-xs)`

### D10 — Indicador de cor do receptor (ponto colorido)

**Decisão**: No `<td class="row-label">`, adicionar `<span>` com círculo de 7px antes do nome quando o receptor tem cor definida em `_allReceptors`. Quando não tem cor: renderiza sem o span.

**Forma**: `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{color};margin-right:5px;vertical-align:middle;flex-shrink:0"></span>` + nome truncado.

**Alternativas consideradas**:
- Borda lateral colorida (border-left 3px) — rejeitado: layout com sticky pode criar artefatos visuais.
