# Implementation Plan: Visões de Consentimentos Ativos no Dashboard

**Branch**: `002-active-consents-views` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-active-consents-views/spec.md`

---

## Summary

Adicionar uma nova página ao dashboard (`/active-consents`) com 5 visões analíticas sobre a tabela `active_consents` (coletada pela feature `001-active-consents`):

1. **Evolução temporal** — gráfico de linhas (Chart.js) com séries por receptor ou transmissor
2. **Matriz receptor × transmissor** — heatmap HTML com intensidade proporcional ao volume
3. **Ranking top-10** — receptores e transmissores por volume de ativos, com Δ% semanal
4. **Intensidade de uso** — razão ativos ÷ clientes únicos por receptor (JOIN com `unique_consents`)

Implementação: novo router `dashboard/routers/active_consents.py` (4 endpoints), nova página `dashboard/gui/active_consents.html`, e ajustes pontuais em `server.py` (registro do router, rota HTML, índices). Zero mudanças no `data-loader`.

---

## Technical Context

**Language/Version**: Python 3.11+ (dashboard) + Vanilla JS (frontend)

**Primary Dependencies**: FastAPI + Uvicorn (backend), Chart.js 4.x CDN (frontend), sqlite3 stdlib

**Storage**: SQLite — tabelas `active_consents` e `unique_consents` (read-only no dashboard)

**Testing**: pytest + httpx.AsyncClient (HTTP-level tests conforme Constituição II)

**Target Platform**: Google Cloud Run (dashboard) + browser desktop (frontend)

**Project Type**: Web service (FastAPI) + static HTML frontend

**Performance Goals**: todos os endpoints `/api/active-consents/*` respondem em < 500ms p95 (Constituição IV)

**Constraints**: Chart.js apenas (sem D3, Plotly, React); vanilla JS (sem bundler); sqlite3 stdlib (sem ORM); SQLite read-only no dashboard

**Scale/Scope**: ~50 receptores × ~100 transmissores = ~5.000 pares por semana; até 52 semanas de histórico

---

## Constitution Check

*GATE: verificado antes do Phase 0. Re-verificado pós-design.*

- [x] **I. Code Quality**: Sem nova abstração sem ≥3 call sites. `_build_color_map()` já tem 5+ usos em `server.py`. Anotações de tipo em todas as funções públicas do novo router. Sem código morto.

- [x] **II. Testing**: Novo endpoint FastAPI → testes HTTP-level com `httpx.AsyncClient` em `tests/test_active_consents_api.py` (happy path + empty period + receptor filter). Heatmap HTML → validação manual obrigatória conforme checklist em `quickstart.md`.

- [x] **III. UX Consistency**: Cores de séries por instituição via `_build_color_map()` (padrão estabelecido, usa `BRAND_COLORS` de `constants.py`). Filtro de período (`start`/`end`) com mesmo comportamento dos endpoints existentes. Heatmap usa a semana mais recente dentro do período selecionado — sem filtros próprios. **Nota justificada**: `API_GROUPS` não se aplica a séries de instituições (é para grupos de API); `_build_color_map()` é o padrão canônico para este caso, em uso em todos os endpoints existentes.

- [x] **IV. Performance**: Dois índices compostos criados via `_ensure_active_consents_indexes()` no `lifespan`. Sem JOINs multi-dimensionais em hot paths — cada endpoint faz uma query simples. Sem pré-agregação adicional (dados já semanais; benchmark mostrará se necessário). `PRAGMA busy_timeout = 3000` preservado.

- [x] **V. Paradigm**: Dashboard lê `active_consents` e `unique_consents`, sem write. Sem importações cross-component. SQL parametrizado (nenhum f-string com input de usuário). Schema não muda — apenas índices adicionais (operação additive-only).

---

## Project Structure

### Documentation (this feature)

```text
specs/002-active-consents-views/
├── plan.md              # Este arquivo
├── spec.md
├── research.md          # Phase 0 ✓
├── data-model.md        # Phase 1 ✓
├── quickstart.md        # Phase 1 ✓
├── contracts/
│   └── api-active-consents.md   # Phase 1 ✓
└── tasks.md             # Gerado por /speckit-tasks
```

### Source Code (alterações)

```text
dashboard/
├── routers/
│   ├── openfinance.py        (existente — sem alteração)
│   └── active_consents.py    (NOVO — 4 endpoints)
├── gui/
│   ├── dashboard.html        (MODIFICAR — link de navegação)
│   ├── receptor_profile.html (MODIFICAR — link de navegação)
│   └── active_consents.html  (NOVO — 5 visões analíticas)
└── server.py                 (MODIFICAR — router + rota HTML + índices)

tests/
└── test_active_consents_api.py  (NOVO — testes HTTP-level)
```

**Structure Decision**: Web application (FastAPI backend + HTML frontend). Padrão idêntico ao de `routers/openfinance.py` servindo `receptor_profile.html`.

---

## Phase 0: Research

**Status**: ✅ Completo — ver [research.md](research.md)

Decisões resolvidas:
- **R-01** Heatmap: tabela HTML + JS (sem dependência adicional)
- **R-02** Cores: `_build_color_map()` existente (BRAND_COLORS + FALLBACK_COLORS)
- **R-03** Δ%: calculado em Python com dois SELECTs (semana atual vs anterior)
- **R-04** Índices: `idx_active_date_receptor` e `idx_active_date_transmitter`
- **R-05** Localização: novo router `routers/active_consents.py`
- **R-06** Página: nova `active_consents.html` em `/active-consents`
- **R-07** JOIN intensidade: `LEFT JOIN unique_consents ON (receptor_uuid, date)`

---

## Phase 1: Design & Contracts

**Status**: ✅ Completo

- [data-model.md](data-model.md) — tabelas consumidas, índices novos, queries de referência
- [contracts/api-active-consents.md](contracts/api-active-consents.md) — 4 endpoints + rota HTML
- [quickstart.md](quickstart.md) — guia de implementação, trechos de código, checklist manual, SQL de verificação

---

## Complexity Tracking

> Nenhuma violação de Constituição identificada. Seção vazia.
