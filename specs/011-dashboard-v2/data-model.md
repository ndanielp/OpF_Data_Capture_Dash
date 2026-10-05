# Data Model — Dashboard 2.0

Todas as mudanças de banco são **aditivas** (Princípio V) e escritas só pelo `data-loader`. O dashboard só lê.

## Tabelas existentes usadas (sem alteração de esquema)

| Tabela | Uso no 2.0 |
|---|---|
| `unique_consents` (date, receptor, receptor_uuid, cpf, cnpj, total) | Rankings e evolução de únicos PF (`cpf`), PJ (`cnpj`) e total; denominador de "por consentimento/mês"; piso de 30 mil |
| `active_consents` (date, receptor_uuid, receptor, transmitter_uuid, transmitter, total, …) | Ranking e evolução de ativos (soma por receptor); evolução por transmissor; "de onde vêm os consentimentos" |
| `api_group_weekly` (date, receptor_uuid, receptor, grp, req_week, consents_total) | Mix de API por grupo e chamadas por grupo com tendência (status 200) |
| `behavior_signals` (week, signal_type, metric, api_group, receptor_uuid, receptor, value_prev, value_curr, change_pct, volume) | "O que mudou?", resumo na aba 1, alertas da instituição |
| `behavior_signals_run` (id=1, computed_at, consents_through, api_through, api_skipped_weeks) | Datas do cabeçalho e do rodapé de alertas |

## Tabelas novas

### `api_status_weekly`

Pré-agregação de chamadas por status (Decisão 2). Reconstruída inteira por `scrapers.refresh_api_status_weekly(con)`.

| Coluna | Tipo | Regra |
|---|---|---|
| `date` | TEXT | semana (YYYY-MM-DD), mesma de `api_requests` |
| `receptor_uuid` | TEXT | |
| `receptor` | TEXT | nome como em `api_requests` |
| `transmitter_uuid` | TEXT | |
| `transmitter` | TEXT | |
| `status` | INTEGER | 200 ou 500 |
| `total` | INTEGER | `SUM(api_requests.total)` |

- PK: (`date`, `receptor_uuid`, `transmitter_uuid`, `status`).
- Índices: (`date`), (`receptor_uuid`, `date`).
- Fonte: `api_requests WHERE api <> 'consents'` — todos os grupos, inclusive `resources` (mesma base dos totais do legado).
- Tamanho esperado: ~170 mil linhas; reconstrução ~35 s.
- Invariante: para cada (date, receptor), `SUM(total) WHERE status=200` = `SUM(req_week)` de `api_group_weekly` (teste de integração).

### `behavior_watch`

Condições de alerta de API "em observação" (Decisão 3). Reconstruída na mesma transação de `behavior_signals`.

| Coluna | Tipo | Regra |
|---|---|---|
| `week` | TEXT | semana mais recente com dados de API em que a condição foi vista |
| `confirm_week` | TEXT | semana seguinte, que confirma ou descarta |
| `direction` | TEXT | `increase` ou `decrease` |
| `receptor_uuid` | TEXT | |
| `receptor` | TEXT | nome mais recente |
| `api_group` | TEXT | slug de `API_GROUPS` (sem `Resource`) |
| `value_prev` | REAL | média das 4 semanas-base |
| `value_curr` | REAL | média das 4 semanas recentes |
| `change_pct` | REAL | variação relativa ao ecossistema |

- PK: (`week`, `receptor_uuid`, `api_group`).
- Contém só condições **sem** alerta confirmado no mesmo evento; esvazia quando a semana de confirmação chega (rebuild).
- Mesmos limites e pisos da regra de API da feature 010 (−40% / +100%, base ≥ 1 mi chamadas/semana, trava de cobertura).

## Mudança de regra (sem mudança de esquema)

- `signals.detect_consent_changes`: elegibilidade = consentimentos **únicos** da semana-base ≥ `CONSENT_FLOOR` (30.000), para `unique_consents` e `active_consents` (Decisão 4).

## Entidades de leitura (respostas da API v2)

### Instituição

`{ uuid, name, group }` — `name` = nome mais recente; `group` = `resolve_institution_group(name)` ∈ {incumbentes, neo_banks, itps, outros}.

### Linha de ranking

| Campo | Regra |
|---|---|
| `rank` | posição no ecossistema inteiro, antes de exclusões e filtros de grupo |
| `uuid`, `name`, `group` | |
| `value` | valor da semana (únicos PF/PJ, ativos ou chamadas) |
| `share` | `value ÷ total do ecossistema` (sempre sobre o total, mesmo com filtros) |
| `pace` | `{per_day, pct_per_day, prev_per_day, trend: up|down|flat}` (Decisão 5) |
| `growth` | `{kind: pct|multiplier|debut|no_base, value, debut_month}` (Decisão 6) |
| `per_consent_month` | só API: chamadas × 30 ÷ (únicos × 7) |
| `error_rate` | só API com status ≠ 200: erros ÷ (sucessos + erros) |
| `pinned` | está em "Sempre mostrar" |
| `below_cut` | fixada fora do Top N (exibida abaixo da linha tracejada) |

Regras de montagem: ordenar pelo critério escolhido → remover `excluded` → aplicar filtro de grupos (fixadas sempre passam) → cortar em N (padrão 15) → anexar fixadas fora do corte com `below_cut=true`.

### Evento de mudança (aba "O que mudou?")

`{ institution, kind: decrease|increase|oscillation|new_entrant, max_abs_change, streak_months, items[{week, metric, api_group, value_prev, value_curr, change_pct}], previous_month_summary }` — agrupado por instituição; ordenado por `max_abs_change`.

### Preferências (navegador)

- `localStorage['opf:v2:ranking']` = `{ pinned: [uuid], excluded: [uuid], sort: total|pace|growth|per_consent, initialized: true }`. Ausente → `pinned = [uuid do Bradesco]`.
- `sessionStorage['opf:v2:filters']` = `{ start, end, period, groups: [slug], metric, institutions: [uuid], institution, compare }`.
- `localStorage['opf:v2:theme']` = `light` (padrão) | `dark`.

## Transições

- `behavior_watch` → `behavior_signals`: na semana de confirmação, se a condição se mantém, o rebuild grava o alerta e a condição sai de `behavior_watch`; se não se mantém, apenas sai.
