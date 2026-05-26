# Implementation Plan: Melhorias no Dashboard de Consentimentos Ativos

**Branch**: `007-active-consents-improvements` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)

## Summary

Sete melhorias no dashboard de Consentimentos Ativos e Ecossistema:
1. **Tornado** de top receptores × transmissores com layout responsivo lado a lado com o gráfico de evolução.
2. **Totais na matriz**: linha e coluna fixadas em primeira posição, excluídas da ordenação interativa.
3. **Números abreviados na matriz**: "1,51 k" / "1,51 M" (pt-BR).
4. **Rename de tabs**: "Ativos" → "Consentimentos Ativos"; "Perfil Receptores" → "Perfil Receptor".
5. **Reordenação de tabs**: Ecossistema → Consentimentos Ativos → Perfil Receptor.
6. **Rename de gráfico no Ecossistema**: "Evolução Consentimentos" → "Evolução Consentimentos Únicos".

Mudanças restritas a três arquivos HTML. Sem alterações de backend, sem novos endpoints, sem schema DB.

## Technical Context

| Item | Decisão |
|---|---|
| Arquivos alvo | `dashboard/gui/active_consents.html` (principal) + `dashboard/gui/dashboard.html` + `dashboard/gui/receptor_profile.html` |
| Backend | Sem alterações |
| Dados do tornado | `/api/active-consents/ranking?by=receptor&limit=10` + `?by=transmitter&limit=10` (já existem) |
| CSS do tornado | Copiado de `receptor_profile.html` (padrão `.tornado-*` estabelecido) |
| Totais da matriz | Calculados client-side em `renderMatrix()` — sem nova API |
| Formato abreviado | Nova `_fmtShort()` — usada somente na matriz |
| Dependências novas | Nenhuma |

## Constitution Check

| Princípio | Status | Justificativa |
|---|---|---|
| I — Simplicidade | ✓ | `_fmtShort` tem 2+ call sites (células + tooltip + totais da matriz); `renderTornado()` tem 1 call site mas ≥ 15 linhas — helper justificado por complexidade |
| II — Testes | ✓ | UI change → validação manual no browser (Constituição II — Frontend); quickstart.md define 14 cenários |
| III — UX Consistency | ⚠ | Cores do tornado (`#4A9EFF`, `#14B8A6`) não vêm de `API_GROUPS` — exceção semântica (cores direcionais receptor/transmissor), mesmo precedente de `receptor_profile.html` |
| IV — Performance | ✓ | Dois fetches paralelos de ranking já existentes; totais calculados in-memory O(n×m); sem nova query |
| V — Paradigma | ✓ | Vanilla JS; três arquivos HTML; sem novos endpoints; sem schema change |
| VI — UI Shell Contract | ⚠ | Tab order e nomes divergem de §6.2 — esta feature amenda o contrato; §6.2 deve ser atualizado após merge (A9) |

## File Structure

```
dashboard/gui/active_consents.html   ← mudanças principais
dashboard/gui/dashboard.html         ← tab rename/reorder + chart title
dashboard/gui/receptor_profile.html  ← tab rename/reorder
specs/006-active-consents-improvements/
├── plan.md
├── research.md
├── quickstart.md
└── tasks.md
```

## Architecture Decisions

### A1 — Tornado: novo card em layout two-col com o card de evolução

O card de evolução (atualmente single-column) é envolvido num `<div class="two-col">` junto com o novo card de tornado. O `.two-col` existente já tem o breakpoint correto (≥ 900 px lado a lado, < 900 px empilhado).

```html
<!-- ANTES: Card 1 sozinho -->
<div class="chart-card" id="card-evolution"> ... </div>

<!-- DEPOIS: dois cards lado a lado -->
<div class="two-col" id="row-evo-tornado">
  <div class="chart-card" id="card-evolution"> ... </div>
  <div class="chart-card" id="card-tornado-active">
    <div class="chart-head">
      <div>
        <div class="chart-title">Tornado — Top Receptores × Transmissores</div>
        <div class="chart-subtitle" id="tornado-active-subtitle">Semana mais recente · Top 10</div>
      </div>
    </div>
    <div class="tornado-header">
      <div class="tornado-header-left">← Receptores</div>
      <div class="tornado-header-center">Instituição</div>
      <div class="tornado-header-right">Transmissores →</div>
    </div>
    <div id="tornado-active-container"></div>
  </div>
</div>
```

### A2 — CSS do tornado: cópia de receptor_profile.html

Copiar o bloco `.tornado-*` de `receptor_profile.html` para `active_consents.html`, substituindo `#tornadoContainer` por `#tornado-active-container`.

```css
/* TORNADO — baseado em receptor_profile.html */
.tornado-row { display:flex; align-items:center; gap:0; height:28px; cursor:default }
.tornado-name { width:140px; font-size:10px; color:var(--text-secondary); text-align:center;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex-shrink:0 }
.tornado-left-bar  { flex:1; display:flex; justify-content:flex-end; align-items:center; gap:3px }
.tornado-right-bar { flex:1; display:flex; justify-content:flex-start; align-items:center; gap:3px }
.t-bar { height:16px; border-radius:2px; min-width:2px; transition:width 0.4s ease }
.t-bar-left  { background:linear-gradient(to left,#4A9EFF,#2563EB) }
.t-bar-right { background:linear-gradient(to right,#14B8A6,#0D9488) }
.tornado-value { font-size:10px; color:var(--text-muted); font-variant-numeric:tabular-nums; min-width:36px }
.tornado-value-left  { text-align:right }
.tornado-value-right { text-align:left }
.tornado-missing { font-size:9px; color:var(--text-muted); font-style:italic; padding:0 4px }
#tornado-active-container {
  height:280px; overflow-y:auto; padding-right:4px; scroll-behavior:smooth;
}
#tornado-active-container::-webkit-scrollbar { width:4px }
#tornado-active-container::-webkit-scrollbar-track { background:var(--bg-base); border-radius:4px }
#tornado-active-container::-webkit-scrollbar-thumb { background:var(--border-default); border-radius:4px }
.tornado-header { display:flex; align-items:center; gap:0; margin-bottom:var(--s2) }
.tornado-header-left   { flex:1; text-align:right; font-size:var(--tx-xs); font-weight:600;
  color:#4A5270; padding-right:var(--s3) }
.tornado-header-center { width:140px; flex-shrink:0; text-align:center; font-size:var(--tx-xs);
  color:var(--text-muted); font-weight:600 }
.tornado-header-right  { flex:1; text-align:left; font-size:var(--tx-xs); font-weight:600;
  color:#14B8A6; padding-left:var(--s3) }
```

### A3 — renderTornado(): nova função JS

```js
function renderTornado(recItems, txmItems) {
  const container = document.getElementById('tornado-active-container');
  if (!container) return;

  if (!recItems || recItems.length === 0) {
    container.innerHTML = '<div style="padding:var(--s4);color:var(--text-muted);font-size:var(--tx-xs);text-align:center">Sem dados disponíveis.</div>';
    return;
  }

  const sorted = [...recItems].sort((a, b) =>
    b.total !== a.total ? b.total - a.total : a.name.localeCompare(b.name)
  );
  const txmMap = Object.fromEntries((txmItems || []).map(d => [d.name, d.total]));
  const scaleMax = Math.max(
    ...sorted.map(d => d.total),
    ...(txmItems || []).map(d => d.total),
    1
  );
  const BAR_MAX_PX = 120;
  const barW = v => Math.round((v / scaleMax) * BAR_MAX_PX);

  container.innerHTML = sorted.map(rec => {
    const txmVal = txmMap[rec.name] ?? null;
    const lw = barW(rec.total);
    const rw = txmVal !== null ? barW(txmVal) : 0;
    const nameShort = rec.name.length > 18 ? rec.name.slice(0, 18) + '…' : rec.name;
    const tooltip = `${rec.name}\nReceptor: ${_fmtShort(rec.total)}\nTransmissor: ${txmVal !== null ? _fmtShort(txmVal) : '—'}`;

    const leftSide = `<div class="tornado-value tornado-value-left">${_fmtShort(rec.total)}</div>
                      <div class="t-bar t-bar-left" style="width:${lw}px"></div>`;
    const rightSide = txmVal !== null
      ? `<div class="t-bar t-bar-right" style="width:${rw}px"></div>
         <div class="tornado-value tornado-value-right">${_fmtShort(txmVal)}</div>`
      : '<span class="tornado-missing">—</span>';

    return `<div class="tornado-row" title="${tooltip}">
      <div class="tornado-left-bar">${leftSide}</div>
      <div class="tornado-name" title="${rec.name}">${nameShort}</div>
      <div class="tornado-right-bar">${rightSide}</div>
    </div>`;
  }).join('');
}
```

### A4 — Integração em loadRanking(): reutilizar respostas já buscadas

```js
async function loadRanking() {
  setCardLoading('card-ranking-receptor', true);
  setCardLoading('card-ranking-transmitter', true);
  setCardLoading('card-tornado-active', true);   // ← adicionar

  const qs = buildQS({ end: _filters.end });
  const [recRes, txmRes] = await Promise.allSettled([
    fetch(`/api/active-consents/ranking?by=receptor&limit=10&${qs}`).then(r => r.json()),
    fetch(`/api/active-consents/ranking?by=transmitter&limit=10&${qs}`).then(r => r.json()),
  ]);

  // ... renderização existente dos cards de ranking (não muda) ...

  // Tornado: reutilizar os mesmos dados
  const recItems = recRes.status === 'fulfilled' ? recRes.value.items : [];
  const txmItems = txmRes.status === 'fulfilled' ? txmRes.value.items : [];
  renderTornado(recItems, txmItems);

  setCardLoading('card-tornado-active', false);  // ← adicionar
}
```

### A5 — Totais da matriz em renderMatrix()

Calcular `rowTotals[]`, `colTotals[]` e `grandTotal` a partir de `values[][]` antes de construir o HTML.

**thead** — adicionar `<th>Total</th>` como segunda coluna (após `row-header`, antes das colunas de transmissores). Sem `data-col-idx` — não clicável para ordenação.

**tbody — linha de totais** — primeiro `<tr>` do `<tbody>`, antes do `rowPerm.forEach`. Células de background `var(--bg-elevated)` para distinguir visualmente dos dados. Célula de intersecção exibe `grandTotal`.

**tbody — células de total por linha** — em cada linha de receptor, inserir ANTES das células de transmissores (mas depois do `td.row-label`) uma célula mostrando `rowTotals[i]`.

Cells de total usam `_fmtShort()` e seguem a mesma convenção de zero (`—`).

Células de total NÃO têm `data-col-idx` ou `data-row-idx` → event listener de sort ignora automaticamente.

### A6 — _fmtShort(): inserir junto com _fmt()

```js
function _fmtShort(n) {
  if (n == null) return '—';
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace('.', ',') + ' M';
  if (n >= 1e3) return (n / 1e3).toFixed(2).replace('.', ',') + ' k';
  return n.toLocaleString('pt-BR');
}
```

Substituir `_fmt(v)` por `_fmtShort(v)` em:
- Células de dados da matriz (`renderMatrix()`)
- Tooltip da matriz (`showTip()` / `_fmt(Number(td.dataset.val))`)
- Células e linha de totais (usando `_fmtShort` diretamente)

`_fmt()` permanece inalterado — ainda usado em gráfico de evolução, rankings e intensidade.

### A7 — Rename e reorder de tabs: os 3 arquivos

**active_consents.html**:
```html
<!-- ANTES -->
<title>Ativos — Open Finance Brasil</title>
...
<a href="/">Ecossistema</a>
<a href="/profile">Perfil Receptores</a>
<a href="/active-consents">Ativos</a>  ← ativo

<!-- DEPOIS -->
<title>Consentimentos Ativos — Open Finance Brasil</title>
...
<a href="/">Ecossistema</a>
<a href="/active-consents">Consentimentos Ativos</a>  ← ativo (movida para 2ª posição)
<a href="/profile">Perfil Receptor</a>
```

**dashboard.html** (mesma reordenação, sem tab ativa):
```html
<a href="/">Ecossistema</a>  ← ativo
<a href="/active-consents">Consentimentos Ativos</a>
<a href="/profile">Perfil Receptor</a>
```

**receptor_profile.html** (mesma reordenação, tab Perfil Receptor ativa):
```html
<a href="/">Ecossistema</a>
<a href="/active-consents">Consentimentos Ativos</a>
<a href="/profile">Perfil Receptor</a>  ← ativo
```

### A8 — Rename do gráfico no Ecossistema (dashboard.html)

```html
<!-- ANTES -->
<div class="chart-title">Evolução Consentimentos</div>

<!-- DEPOIS -->
<div class="chart-title">Evolução Consentimentos Únicos</div>
```

### A9 — Follow-up: atualizar Constituição §6.2 (não parte desta feature)

Após merge, criar PR separado para atualizar `.specify/memory/constitution.md` §6.2:
- Nova ordem canônica: Ecossistema → Consentimentos Ativos → Perfil Receptor
- Novos nomes: "Consentimentos Ativos" e "Perfil Receptor"
- MINOR amendment (nova sub-seção, nomes atualizados)

## Implementation Order

```
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009
```

### Parallel Opportunities

```
T001 ‖ T006 ‖ T007   (CSS/JS edits independentes — mesmo arquivo mas conteúdo disjunto)
T005 ‖ T006 ‖ T007   (CSS + rename tabs + rename chart são independentes entre si)
```

Ver `tasks.md` para detalhes.
