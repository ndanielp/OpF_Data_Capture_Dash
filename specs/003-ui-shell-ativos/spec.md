# Spec: Consistência do Shell de UI — Página Ativos

**Feature**: `003-ui-shell-ativos`
**Branch**: `003-ui-shell-ativos`
**Status**: Pronto para implementação

---

## Análise: Contrato Visual das Páginas Existentes

Antes das histórias de usuário, esta seção documenta o padrão canônico
extraído de `dashboard.html` (Ecossistema) e `receptor_profile.html`
(Perfil Receptores) — as duas páginas de referência.

### 1. Shell — Estrutura DOM

```
<body>                         ← height:100vh; flex-direction:column; overflow:hidden
  <div class="titlebar">       ← 38px, --bg-elevated, border-bottom subtle
  <div class="app-body">       ← flex:1; display:flex; overflow:hidden
    <aside class="sidebar">    ← width:224px; flex-shrink:0
    <main  class="main-content"> ← flex:1; overflow-y:auto
  <div class="status-bar">     ← 28px, --bg-elevated, border-top subtle (opcional)
```

### 2. Titlebar

| Elemento | Valor canônico |
|---|---|
| Logo badge | `<div class="titlebar-logo">OF</div>` — 20×20px, bg=`--text-accent`, border-radius=`--r-sm`, texto branco bold |
| Nome do app | `<span class="titlebar-name">Open Finance Brasil</span>` — 12px, weight 600 |
| Separador | `›` em `--text-muted` |
| **Nav tab group** | Container com `background:rgba(0,0,0,0.1)`, `padding:3px`, `border-radius:var(--r-md)`, `border:1px solid var(--border-subtle)` |
| Tab inativa | `color:var(--text-secondary)`, `font-weight:500`, `padding:3px 12px`, `border-radius:var(--r-sm)` |
| Tab ativa | `color:var(--text-primary)`, `font-weight:600`, `background:var(--bg-hover)`, `box-shadow:0 1px 2px rgba(0,0,0,0.2)` |
| Spacer | `<div class="titlebar-spacer">` — `flex:1` |
| Theme toggle | `<button id="theme-toggle" class="theme-btn">☀️/🌙</button>` |

**Tabs obrigatórias** (sempre 3, na ordem):
1. `Ecossistema` → `/`
2. `Perfil Receptores` → `/profile`
3. `Ativos` → `/active-consents`

### 3. Sidebar (224px)

```
.sidebar
  .sidebar-inner (flex:1; overflow-y:auto)
    .sidebar-group      ← grupo "Receptores"
      .sidebar-group-header
        .sidebar-group-label   ← "RECEPTORES" uppercase, --text-muted, 11px
        .sidebar-group-badge   ← contagem, --bg-elevated pill
      input.sidebar-search     ← placeholder "Filtrar receptores…"
      ul.receptor-list
        li.receptor-item[.selected][.inactive]
          .receptor-dot         ← 8px círculo colorido
          .receptor-name        ← truncado com ellipsis
    .sidebar-group      ← grupos contextuais adicionais (opcional)
  .sidebar-footer (flex-shrink:0; border-top)
    .last-updated               ← dot verde + texto data
    button.btn-refresh          ← ícone ↻ + "Recarregar dados"
```

**Comportamento de seleção** (multi-select):
- Click simples → deseleciona todos, seleciona o clicado (modo único)
- Click com Ctrl/Meta/Shift → toggle do item (modo multi)
- Item `.selected` → `background:rgba(74,158,255,0.1)`
- Item `.inactive` (sem dados recentes) → `color:--text-muted`; dot usa `--border-default`

**Receptor list → API**: nomes selecionados concatenados como `receptors=A,B,C`
(substring match — mesmo padrão dos outros endpoints).

### 4. Date Bar (barra flutuante de período)

Posição: **primeiro filho** de `.main-content`, `position:sticky; top:0; z-index:10`.

```
.date-bar (--bg-elevated; border --border-subtle; border-radius --r-md; padding --s2 --s4)
  span.date-bar-label  "PERÍODO"
  .date-inputs
    input.date-field#date-start  type="date"
    span.date-arrow  "→"
    input.date-field#date-end    type="date"
  .date-spacer (flex:1)
  .quick-ranges
    button.quick-btn[data-months="0.25"]  "7d"
    button.quick-btn[data-months="1"]     "30d"
    button.quick-btn[data-months="3"]     "3m"
    button.quick-btn[data-months="6"]     "6m"
    button.quick-btn.active[data-months="12"]  "1a"  ← padrão ativo
    button.quick-btn[data-months="ytd"]   "Ano atual"
    button.quick-btn[data-months="0"]     "Tudo"
  .date-spacer (flex:1)
  [slots para controles adicionais — ex: toggles de view]
```

**Quick range logic** (usa `_dbMaxDate` como ponto de referência quando disponível):
- `"0"` → `_dbMinDate` ou `'2020-01-01'`
- `"ytd"` → primeiro dia do ano de `_dbMaxDate`
- valor numérico < 1 → subtrai `Math.round(months×30)` dias
- valor numérico ≥ 1 → subtrai meses inteiros

### 5. Theme Toggle

```js
// Lê tema salvo no load
let currentTheme = localStorage.getItem('theme') || 'dark';
document.body.setAttribute('data-theme', currentTheme);

// Ao clicar
currentTheme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
document.body.setAttribute('data-theme', currentTheme);
localStorage.setItem('theme', currentTheme);
applyThemeColorsToCharts();
```

`applyThemeColorsToCharts()` atualiza `Chart.defaults.color`, `grid.color`,
`tooltip.backgroundColor/borderColor/titleColor` em todos os gráficos ativos,
chamando `chart.update()`.

Tokens light (em `[data-theme="light"]`):
```css
--bg-base: #F3F4F6;  --bg-surface: #FFFFFF;  --bg-elevated: #E5E7EB;
--bg-hover: #D1D5DB; --text-primary: #111827; --text-secondary: #4B5563;
--text-muted: #6B7280; --border-subtle: #D1D5DB; --border-default: #9CA3AF;
```

### 6. Cards de Gráfico

```css
.chart-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-lg);
  padding: var(--s5);
  position: relative;
  overflow: hidden;
}
/* Loading sweep */
.chart-card.card-loading::after {
  content: '';
  position: absolute;
  top: 0; left: -60%; width: 60%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--text-accent), transparent);
  animation: card-sweep 1.1s linear infinite;
}
.chart-card.card-loading canvas,
.chart-card.card-loading table { opacity: 0.35; }
```

Cabeçalho interno: `.chart-head` (flex, space-between) → `.chart-title` (17px,
weight 600) + `.chart-subtitle` (12px, `--text-secondary`).

Estado vazio: `<div class="chart-empty">` — 120px height, centered, `--text-muted`.

### 7. Design Tokens Canônicos

```css
/* Espaçamento */
--s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:20px; --s6:24px; --s8:32px;

/* Tipografia */
--tx-xs:11px; --tx-sm:12px; --tx-base:13px; --tx-md:15px; --tx-lg:17px; --tx-xl:20px;

/* Radii */
--r-sm:4px; --r-md:8px; --r-lg:12px;
```

> **Atenção**: `active_consents.html` usa `--radius-sm/md/lg` (valores diferentes:
> 6/10/16px). A migração para `--r-sm/md/lg` é obrigatória.

### 8. Persistência de Filtros (`sessionStorage`)

Chave: `'opf:filters'`. JSON com campos:
```json
{ "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "receptors": "A,B", "status": "200", "normalize": "1", "institution": "<uuid>" }
```
Campos relevantes para Ativos: `start`, `end`, `receptors`.

---

## Divergências Atuais em `active_consents.html`

| Componente | Estado atual | Estado alvo |
|---|---|---|
| Layout macro | `<nav>` no topo + `<main class="page">` centralizado | `titlebar` + `app-body` → `sidebar` + `main-content` |
| Body | `min-height:100vh` scroll livre | `height:100vh; overflow:hidden` |
| Navegação | `<nav>` simples | Tabs na titlebar (padrão canônico) |
| Filtro de receptor | Campo texto na `.filter-bar` | Sidebar com lista clicável + dots coloridos |
| Filtro de data | Inputs na `.filter-bar` | `.date-bar` sticky com quick-range buttons |
| Theme toggle | Ausente | `<button id="theme-toggle">` na titlebar |
| Tokens de raio | `--radius-sm/md/lg` (6/10/16px) | `--r-sm/md/lg` (4/8/12px) |
| Cards | `.card` custom | `.chart-card` com `.card-loading` sweep |
| Loading state | Ausente | Sweep animation por card |
| Status bar | Ausente | Opcional (pode omitir em Ativos) |
| sessionStorage | Ausente | `'opf:filters'` {start, end, receptors} |
| Botão aplicar | `.btn-apply` explícito | Sem botão — filtros aplicam ao mudar (como nas outras páginas) |

---

## Histórias de Usuário

### US1 — Shell Completo (P1, MVP)

**Como** usuário que navega entre Ecossistema, Perfil e Ativos,  
**quero** que a página Ativos tenha exatamente a mesma estrutura visual
(titlebar, sidebar, date bar, theme toggle)  
**para que** eu não precise reaprender a interface ao mudar de visão.

**Critérios de aceite**:
- [ ] Titlebar de 38px com logo "OF", nome, nav-tabs (Ecossistema / Perfil Receptores / **Ativos** ativo), spacer, theme toggle
- [ ] Sidebar de 224px à esquerda com grupo "Receptores": search input + lista com dots coloridos, badge de contagem, footer com data de referência
- [ ] `.main-content` ocupa o espaço restante, `overflow-y:auto`
- [ ] Tema dark/light alterna via botão na titlebar, persiste em `localStorage`, atualiza cores do Chart.js

### US2 — Date Bar com Quick Ranges (P1, MVP)

**Como** usuário analisando a evolução de consentimentos ativos,  
**quero** poder ajustar o período com um clique (7d, 30d, 3m, 6m, 1a, Ano atual, Tudo)  
**para que** a análise temporal seja tão ágil quanto nas outras páginas.

**Critérios de aceite**:
- [ ] `.date-bar` sticky no topo do `main-content`, mesmo estilo visual dos outros
- [ ] Quick-range buttons com comportamento idêntico (usa `_dbMaxDate` como ref)
- [ ] Mudar período recarrega todos os 4 gráficos automaticamente (sem botão "Aplicar")
- [ ] Seleção do receptor na sidebar também recarrega automaticamente

### US3 — Sidebar de Receptores Interativa (P1, MVP)

**Como** usuário que quer focar em um subconjunto de receptores,  
**quero** clicar nos nomes na sidebar para filtrar todos os gráficos da página  
**para que** o fluxo seja idêntico ao da página Ecossistema.

**Critérios de aceite**:
- [ ] Click simples → seleciona apenas aquele receptor (modo single)
- [ ] Click com Ctrl/Meta/Shift → toggle multi-select
- [ ] Nenhum selecionado = todos os receptores (padrão)
- [ ] Receptores sem dados na semana mais recente aparecem com dot cinza (`.inactive`)
- [ ] Campo de busca filtra a lista visualmente (não recarrega dados)

### US4 — Cards com Loading State (P2)

**Como** usuário,  
**quero** ver uma indicação visual enquanto cada gráfico carrega  
**para que** eu saiba que o sistema está respondendo, mesmo com queries lentas.

**Critérios de aceite**:
- [ ] Classe `.card-loading` adicionada ao container do card ao iniciar fetch
- [ ] Sweep animation (linha azul horizontal) visível durante o carregamento
- [ ] Canvas/table opacidade 0.35 durante carregamento
- [ ] Loading removido após receber resposta (sucesso ou erro)

### US5 — Persistência de Filtros via sessionStorage (P2)

**Como** usuário que navega entre páginas,  
**quero** que o período selecionado nos Ativos seja preservado quando volto  
**para que** eu não precise reconfigurar o filtro a cada visita.

**Critérios de aceite**:
- [ ] `{start, end, receptors}` persiste em `sessionStorage['opf:filters']` a cada mudança
- [ ] Ao abrir a página, filtros são restaurados do sessionStorage
- [ ] Compatível com os campos já gravados por Ecossistema e Perfil (não sobrescreve `status`, `normalize`, `institution`)

---

## Âmbito e Não-Âmbito

**Incluído nesta feature**:
- Refatoração visual completa de `active_consents.html`
- Migração de tokens CSS (`--radius-*` → `--r-*`)
- Inclusão no contrato de shell da Constituição

**Não incluído**:
- Mudanças nos endpoints FastAPI (API permanece igual)
- Novos gráficos ou métricas (serão outras features)
- Testes automatizados da UI (Constituição II exige validação manual no browser)
