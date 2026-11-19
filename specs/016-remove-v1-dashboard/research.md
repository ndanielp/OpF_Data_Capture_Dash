# Research: Remover o painel v1 (legado)

**Feature**: [spec.md](spec.md) · **Date**: 2026-11-19

Mapeamento do que é só do v1, do que o Dashboard 2.0 e a exportação usam, e do que fica por segurança. Medido no código da `main` (commit 642bd51).

## R1. O que é v1 e vai embora

| Área | Arquivos / trechos |
|---|---|
| Páginas | `dashboard/gui/dashboard.html` (2952 linhas), `receptor_profile.html` (1642), `active_consents.html` (1469) |
| Rotas de página | `server.py`: `/`, `/profile`, `/active-consents` (viram redirecionamentos) |
| Rotas de API em `server.py` | `/api/receptors`, `/api/consents`, `/api/api-requests`, `/api/api-requests-timeseries`, `/api/resources`, `/api/acceleration`, `/api/efficiency`, `/api/stats` |
| Routers | `routers/openfinance.py` (`/api/of/*`), `routers/active_consents.py` (`/api/active-consents/*`), `routers/signals.py` (`/api/signals`) |
| Serviços | `services/of_analytics.py` (800 linhas, exceto `resolve_institution_group`), `services/cache.py` |
| Em `server.py` | cache de respostas (`cached_response`, `_refresh_cache`, `_get_*`), carregadores (`_load_*`), cores (`_brand_color`, `_build_color_map`), filtros (`_parse_*`, `_filter_*`, `_top10_with_bradesco`), `_get_latest_weeks`, `_warm_profile_cache`, `_signal_from_quantiles`, `_assign_signals`, `_p20_p80`, constantes `_API_LABELS`, `_ORDERED_APIS`, `_NORM_*`, `_FALLBACK_COLORS`, `_BRAND` |
| Testes | `tests/test_active_consents_api.py`, `test_institution_groups.py`, `test_signals_api.py` (só chamam rotas v1) |
| Cabeçalho do v2 | `gui/v2/shell.js:221`, o link "Painel legado" |
| Constituição | §6.1–6.7 (shell legado), trechos dos Princípios III e VI que citam o legado |
| `CLAUDE.md` | seções sobre o painel legado, `Dashboard API` (rotas v1), frases "legacy dashboard" |
| Specs | `specs/002`, `003`, `004`, `005`, `006` e a pasta `especificações/` (PRD do perfil v1 e HTML de exemplo) |

## R2. O que o v2 e a exportação usam e precisa ficar

- `services/of_analytics.resolve_institution_group`: usada por `routers/v2.py` e `services/v2_metrics.py`. Vai para `services/constants.py`, junto de `INSTITUTION_GROUPS`, e os dois imports mudam.
- `services/constants.py`: o v2 usa `API_GROUPS`, `API_LABELS`, `GROUP_COLORS_V2`, `GROUP_COLORS_V2_DARK`, `GROUP_LABELS_V2`, `INSTITUTION_GROUP_SLUGS`, `SHORT_NAMES`; a exportação usa `API_LABELS`. `BRAND_COLORS`, `GROUP_COLORS`, `GROUP_LABELS`, `EXCLUDED_APIS`, `RESOURCES_API` só são lidos pelo v1: confirmar com busca e apagar os que ficarem órfãos.
- `server.py`: ficam `lifespan`, as páginas `/v2*`, `_RevalidatingStatic` e `run_server`; `_warm_v2_cache`; e os três `_ensure_*` (índices e `api_group_weekly`), porque o v2 e a contagem da exportação dependem dessas estruturas na base e a regra é não mudar o comportamento.
- `_db_con()` só é usado por carregadores v1 e pelos `_ensure_*` de índices: fica o necessário para os `_ensure_*`.

## R3. Tabelas da base

Nenhuma tabela, coluna ou índice muda. `api_group_weekly`, `api_status_weekly`, `api_endpoint_weekly`, `behavior_signals` e `behavior_watch` continuam geradas pela coleta e lidas pelo v2.

## R4. Redirecionamento

`GET /`, `/profile` e `/active-consents` respondem 307 para `/v2`. Escolhi 307 (e não 301) para o navegador não guardar o destino de forma permanente caso a raiz volte a ter outro uso. Os parâmetros da URL são descartados. APIs removidas passam a responder 404 do próprio FastAPI.

## R5. Constituição

A remoção do shell legado (§6.1–6.7) e das regras que só o citam é uma mudança MAIOR (1.5.0 → 2.0.0): sai um princípio de interface. O Princípio VI fica só com o shell v2. Os Princípios III e V mantêm as regras de UX e de paradigma, sem as referências ao `opf:filters` e às três páginas.

## R6. Specs a apagar

002, 003, 004, 005 e 006 descrevem só telas de "Consentimentos Ativos" do v1. Ficam: 001 (coleta), 008 (deploy), 009 (grupos de instituições, que o v2 usa), 010 (detecção de mudanças, que alimenta o v2), 011 em diante. As referências do `CLAUDE.md` e do Princípio VI a essas specs saem junto.

## R7. Risco e como medir "sem mudança de comportamento"

Os testes do v2 e da exportação (`test_v2_*.py`) cobrem os valores. Além deles, antes e depois da remoção: comparar `GET /api/v2/meta`, `/ranking`, `/evolution`, `/changes`, `/institution/{uuid}` e uma exportação CSV, na base real, byte a byte.
