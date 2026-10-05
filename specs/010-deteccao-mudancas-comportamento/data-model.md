# Data Model: Detecção de Mudanças de Comportamento

Duas tabelas novas em `consents.db`, criadas por `scrapers.open_db()` (DDL aditivo,
`CREATE TABLE IF NOT EXISTS`) e escritas **somente** por `compute_signals.py`.
Nenhuma tabela existente é alterada.

## `behavior_signals` — um alerta por linha

```sql
CREATE TABLE IF NOT EXISTS behavior_signals (
    week           TEXT    NOT NULL,   -- sexta-feira de referência, YYYY-MM-DD
    signal_type    TEXT    NOT NULL,   -- 'new_entrant' | 'increase' | 'decrease'
    metric         TEXT    NOT NULL,   -- 'unique_consents' | 'active_consents' | 'api_group'
    api_group      TEXT    NOT NULL DEFAULT '',  -- slug de API_GROUPS quando metric='api_group'; '' caso contrário
    receptor_uuid  TEXT    NOT NULL,
    receptor       TEXT    NOT NULL DEFAULT '',
    value_prev     REAL,               -- base de comparação (ver regras); NULL em estreia
    value_curr     REAL    NOT NULL,
    change_pct     REAL,               -- (curr/prev - 1); para API, já descontado o ecossistema; NULL em estreia
    volume         INTEGER NOT NULL DEFAULT 0,   -- consentimentos únicos do receptor na semana (ordenação)
    PRIMARY KEY (week, signal_type, metric, api_group, receptor_uuid)
);
CREATE INDEX IF NOT EXISTS idx_behavior_signals_week ON behavior_signals(week);
```

`api_group` usa `''` em vez de `NULL` porque, no SQLite, `NULL` em chave primária não
colide consigo mesmo — duas linhas iguais com `NULL` seriam aceitas.

### Regras que geram as linhas (spec FR-002 a FR-007)

Constantes num único lugar do topo de `signals.py`:

| Constante | Valor |
|---|---|
| `NEW_ENTRANT_FLOOR` | 30 000 consentimentos únicos |
| `NEW_ENTRANT_GROWTH` | 1,5 (≥ +50%) |
| `NEW_ENTRANT_LOOKBACK` | 4 observações |
| `NEW_WINDOW_WEEKS` | 26 semanas desde a primeira aparição |
| `CONSENT_FLOOR` | 30 000 |
| `CONSENT_UP` / `CONSENT_DOWN` | +0,20 / −0,10 |
| `API_FLOOR` | 1 000 000 chamadas/semana (média da base) |
| `API_UP` / `API_DOWN` | razão relativa > 2,0 / < 0,6 |
| `API_CONFIRM_WEEKS` | 2 |
| `API_COVERAGE_MIN` | 0,70 da mediana das 8 semanas anteriores |

**`new_entrant`** — `metric='unique_consents'`, uma linha por receptor no máximo:
- Receptores presentes na primeira semana da série (jan/2024) nunca são "novos".
- Para cada observação `t` com idade ≤ 26 semanas: dispara na **primeira** `t` em que
  `valor[t] ≥ 30 000` e (`t` é a estreia **ou** `valor[t−4] = 0` **ou**
  `valor[t] ≥ 1,5 × valor[t−4]`), com `t−4` limitado à estreia.
- `value_prev` = `valor[t−4]` (NULL na estreia); `change_pct` idem.

**`increase` / `decrease` de consentimentos** — `metric` = `'unique_consents'` ou
`'active_consents'` (este somado sobre transmissores):
- Elegível: `valor[t−1] ≥ 30 000` **e** idade > 26 semanas.
- `change_pct = valor[t]/valor[t−1] − 1`; `> +0,20` → increase, `< −0,10` → decrease.
- Alerta imediato: uma linha por semana em que a condição ocorre.

**`increase` / `decrease` de uso de API** — `metric='api_group'`, `api_group` = slug
(sem `Resource`):
- Série `req_week` por (receptor, grupo) num eixo de todas as sextas da base.
- `ratio = média(t−3..t) / média(t−7..t−4)`; `eco` = mesma razão para a soma do grupo no
  ecossistema; `rel = ratio / eco`.
- Elegível: `média(t−7..t−4) ≥ 1 000 000`.
- Condição em `t`: `rel > 2,0` (increase) ou `rel < 0,6` (decrease).
- Alerta na **segunda** semana consecutiva da condição (`t` e `t−1` verdadeiras, `t−2`
  falsa) — um alerta por evento.
- `change_pct = rel − 1`; `value_prev` = média da base; `value_curr` = média recente.
- Só em semanas que passam na trava de cobertura (ver abaixo).

## `behavior_signals_run` — metadados da última execução (uma linha)

```sql
CREATE TABLE IF NOT EXISTS behavior_signals_run (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    computed_at        TEXT NOT NULL,   -- ISO 8601 UTC
    consents_through   TEXT,            -- última semana de unique_consents usada
    api_through        TEXT,            -- última semana de api_group_weekly usada
    api_skipped_weeks  TEXT NOT NULL DEFAULT '[]',  -- JSON: semanas que falharam na trava de cobertura
    signals_total      INTEGER NOT NULL DEFAULT 0
);
```

Permite ao card dizer "calculado em …", mostrar se os alertas de API vão até uma semana
anterior à dos consentimentos, e avisar "alertas de API indisponíveis nesta semana:
coleta incompleta" em vez de exibir um vazio enganoso.

## Relacionamentos

```text
unique_consents ─┐
active_consents ─┼─▶ signals.py (regras puras) ─▶ behavior_signals ─▶ GET /api/signals ─▶ card
api_requests ─▶ refresh_api_group_weekly ─▶ api_group_weekly ─┘              ▲
                                                                          resolve_institution_group()
                                                                          (filtro de grupos, na leitura)
```

## Invariantes (verificadas em teste)

1. Rodar `compute_signals.py` duas vezes seguidas produz exatamente as mesmas linhas.
2. Nenhum receptor tem mais de uma linha `new_entrant`.
3. Nenhuma linha `increase`/`decrease` de consentimentos para receptor com idade ≤ 26 semanas.
4. Nenhuma linha de API em semana listada em `api_skipped_weeks`.
