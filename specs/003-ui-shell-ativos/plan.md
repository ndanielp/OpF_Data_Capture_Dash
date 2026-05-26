# Implementation Plan: UI Shell Contract — Página Ativos

## Technical Context

| Item | Decision |
|---|---|
| Arquivo alvo | `dashboard/gui/active_consents.html` (refatoração completa) |
| Backend | Sem alterações — todos os 4 endpoints permanecem idênticos |
| Estratégia | Substituir o shell atual pelo padrão canônico extraído de `dashboard.html` e `receptor_profile.html` |
| Dependências novas | Nenhuma — reutiliza Chart.js já carregado |
| DB / API | Sem mudanças — `GET /api/receptors` já existe; os 4 endpoints `/api/active-consents/*` já existem |

## Constitution Check

| Princípio | Status | Justificativa |
|---|---|---|
| I — Simplicidade | ✓ | Remoção de código próprio; substituição por classes já testadas nas outras páginas |
| II — Testes | ✓ | Validação manual no browser obrigatória (Constituição II — UI); sem novos endpoints |
| **III — UX Consistency** | ✓ | Esta feature É a implementação do Princípio III + VI |
| IV — Performance | ✓ | Sem novas queries; `/api/receptors` já é usado pelas outras páginas |
| V — Paradigma | ✓ | Vanilla JS + HTML; sem bundler; sem framework |
| **VI — UI Shell Contract** | ✓ | Esta feature implementa o contrato definido em VI |

## File Structure

```
dashboard/gui/active_consents.html    ← único arquivo modificado
```

Nenhum arquivo Python é alterado. Nenhuma rota nova.

## Architecture Decisions

### A1 — Shell idêntico ao dashboard.html
Copiar verbatim as classes CSS de `dashboard.html` para o `<style>` de
`active_consents.html`:
- `.titlebar`, `.app-body`, `.sidebar`, `.sidebar-inner`, `.sidebar-group`,
  `.sidebar-group-header`, `.sidebar-group-label`, `.sidebar-group-badge`,
  `.sidebar-search`, `.receptor-list`, `.receptor-item`, `.receptor-dot`,
  `.receptor-name`, `.sidebar-footer`, `.last-updated`, `.btn-refresh`,
  `.main-content`, `.date-bar`, `.date-bar-label`, `.date-inputs`, `.date-field`,
  `.date-arrow`, `.date-spacer`, `.quick-ranges`, `.quick-btn`, `.chart-card`,
  `.chart-head`, `.chart-title`, `.chart-subtitle`, `.chart-empty`,
  `.chart-toggles`, `.theme-btn`

Design tokens (`--r-sm/md/lg`, `--s1..s8`, `--tx-*`) alinhados ao canônico.
`--radius-sm/md/lg` (valores 6/10/16px) serão removidos.

### A2 — Receptor list via `/api/receptors`
A página Ecossistema já faz `GET /api/receptors` e retorna
`[{label, color, top, uuid}]`. A página Ativos usa o mesmo endpoint para
popular a sidebar. Receptores com `top=false` recebem `.inactive`.

### A3 — Filtro de receptor: sidebar → API
O campo `receptors` na sidebar substitui o input de texto no filter-bar.
Multi-select idêntico ao Ecossistema: nomes concatenados `A,B,C`.
Nenhum selecionado → nenhum parâmetro `receptors` enviado (= todos).

### A4 — Date bar com quick ranges
Os 7 botões (7d, 30d, 3m, 6m, 1a, Ano atual, Tudo) com lógica de
`_dbMaxDate` como referência, idêntico ao Ecossistema. `1a` é o padrão ativo.

### A5 — Toggle "Por receptor / Por transmissor"
Será um slot extra na `.date-bar` (após o segundo spacer), usando
`.chart-toggles`. Mantém a funcionalidade atual mas integrado no novo shell.

### A6 — sessionStorage
`'opf:filters'` com campos `{start, end, receptors}`. Lidos no boot e
gravados a cada mudança. Campos de outras páginas (`status`, `normalize`,
`institution`) preservados via spread.

### A7 — Loading state por card
Função `setCardLoading(id, on)` idêntica ao `dashboard.html`.
Chamada no início e fim de cada `fetch` nos 4 loads: `loadEvolution`,
`loadMatrix`, `loadRanking`, `loadIntensity`.

### A8 — Theme toggle
`localStorage.getItem('theme')` no boot. `applyThemeColorsToCharts()`
atualiza Chart.js defaults + todos os charts ativos.

### A9 — Status bar (opcional)
Incluir uma status-bar mínima exibindo a `reference_date` retornada pela
API (indica a semana mais recente disponível no banco).

## Implementation Order

1. **Setup CSS**: tokens + classes shell + light theme override
2. **HTML structure**: titlebar → app-body → sidebar → main-content
3. **Receptor sidebar**: `/api/receptors` fetch + buildReceptorList() + search
4. **Date bar**: inputs + quick-range buttons + handlers
5. **Theme toggle**: localStorage + applyThemeColorsToCharts()
6. **Migrar 4 gráficos**: evoluçao (Chart.js), matrix (table), ranking (bars), intensity (bars) — dentro do novo `.main-content`, usando `.chart-card` + `setCardLoading`
7. **sessionStorage**: read on boot, write on change
8. **Status bar**: reference_date
9. **Validação**: browser manual checklist
