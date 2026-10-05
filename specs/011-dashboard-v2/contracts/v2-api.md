# Contrato — API do Dashboard 2.0 (`/api/v2/*`)

Somente leitura (GET), JSON, servidos pelo mesmo FastAPI do legado. Endpoints do legado não mudam.

**Parâmetros comuns**

| Parâmetro | Formato | Padrão | Regra |
|---|---|---|---|
| `start`, `end` | YYYY-MM-DD | últimos 12 meses até a semana mais recente | data inválida → 422 |
| `groups` | slugs separados por vírgula | todos | mesma semântica da feature 009: slug desconhecido é ignorado |
| `pinned`, `excluded` | UUIDs separados por vírgula | vazio | UUID desconhecido é ignorado |

Erros: 422 para parâmetro inválido (`{"detail": "..."}` legível); tabela ausente (ex.: `api_status_weekly` ou `behavior_signals` ainda não geradas) → 200 com o bloco correspondente vazio e `"unavailable": ["errors"]` / `["signals"]`, nunca 500.

---

## GET `/api/v2/meta`

Dados de cabeçalho e catálogos. Cache 1 h.

```json
{
  "data_through": "2026-08-28",
  "updated_at": "2026-09-23",
  "groups": [{"slug": "neo_banks", "label": "Neobancos", "color": "#5B2BC4"}, "..."],
  "api_groups": [{"slug": "Conta", "label": "Contas", "color": "#4A9EFF"}, "..."],
  "institutions": [{"uuid": "…", "name": "BRADESCO", "short": "Bradesco", "group": "incumbentes"}, "..."]
}
```

---

## GET `/api/v2/ranking`

| Parâmetro | Valores | Padrão |
|---|---|---|
| `metric` | `unique_pf`, `unique_pj`, `active`, `api` | `unique_pf` |
| `limit` | 1–50 | 15 |
| `sort` | `total`, `pace`, `growth`, `per_consent` (só `api`) | `total` |
| `status` (só `api`) | `200`, `500`, `all` | `200` |
| `scale` (só `api`) | `total`, `per_consent` | `total` |

```json
{
  "metric": "unique_pf",
  "week": "2026-08-28",
  "period": {"start": "2025-08-29", "end": "2026-08-28"},
  "ecosystem": {
    "total": 145864692, "receptors": 40,
    "by_group": [{"group": "neo_banks", "value": 62868000, "share": 0.431}],
    "pace": {"per_day": 264578, "prev_per_day": 250064, "trend": "flat"},
    "growth": {"kind": "pct", "value": 1.15},
    "per_consent_month": null, "error_rate": null, "top3_share": null
  },
  "rows": [
    {"rank": 13, "uuid": "…", "name": "Bradesco", "group": "incumbentes",
     "value": 5117241, "share": 0.0351,
     "pace": {"per_day": 7577, "pct_per_day": 0.0015, "prev_per_day": 7684, "trend": "flat"},
     "growth": {"kind": "pct", "value": 1.10, "debut_month": null},
     "per_consent_month": null, "error_rate": null,
     "pinned": true, "below_cut": false}
  ],
  "excluded": [{"uuid": "…", "name": "Shopee", "rank": 6}],
  "filters_label": "sem Shopee"
}
```

Regras: `rank` é a posição no ecossistema; `share` é sobre o total do ecossistema mesmo com `groups`; fixadas fora do corte vêm ao fim com `below_cut: true`; com `status=500`, `value` = erros e `error_rate` preenchido; com `scale=per_consent`, a ordem e `share` seguem `per_consent_month` (`share` = null).

---

## GET `/api/v2/evolution`

| Parâmetro | Valores | Padrão |
|---|---|---|
| `metric` | `unique_pf`, `unique_pj`, `active`, `api` | `unique_pf` |
| `granularity` | `month`, `week` | `month` |
| `institutions` | UUIDs (até 8; com `by=transmitter`, UUIDs de transmissores) | as 5 maiores no fim do período (nos grupos escolhidos) |
| `by` (só `active`) | `receptor`, `transmitter` | `receptor` |
| `start`, `end` | AAAA-MM-DD | 52 semanas até a semana mais recente |
| `groups` | slugs de grupo | todos |

```json
{
  "metric": "unique_pf", "granularity": "month", "by": "receptor",
  "week": "2026-08-28", "period": {"start": "2025-08-29", "end": "2026-08-28"},
  "points": ["2025-08", "2025-09", "..."],
  "headline": {
    "ecosystem_growth": {"kind": "pct", "value": 1.156, "debut_month": null, "from": 67656532, "to": 145864692},
    "top_gainer": {"uuid": "…", "name": "Shopee", "group": "outros", "pp": 5.5, "share": 0.055, "share_start": 0.0,
                   "debut_month": "2025-11", "growth": {"kind": "debut", "value": null, "debut_month": "2025-11"}},
    "top_loser": {"uuid": "…", "name": "Nubank", "group": "neo_banks", "pp": -6.8, "share": 0.151, "share_start": 0.219,
                  "debut_month": null, "growth": {"kind": "pct", "value": 0.49, "debut_month": null}}
  },
  "series": [{"uuid": "…", "name": "Nubank", "group": "neo_banks", "values": [14826174, null, "..."],
              "shares": [0.219, null, "..."], "last": 22044862, "growth": {"kind": "pct", "value": 0.49}}],
  "group_share": [{"point": "2025-08", "neo_banks": 0.465, "itps": 0.248, "incumbentes": 0.265, "outros": 0.022}],
  "group_share_change": [{"group": "neo_banks", "share": 0.431, "pp": -3.4}],
  "share_changes": [{"uuid": "…", "name": "Shopee", "group": "outros", "pp": 5.5, "share": 0.055, "share_start": 0.0,
                     "debut_month": "2025-11", "growth": {"kind": "debut"}}],
  "quarterly_pace": [{"uuid": "…", "name": "Belvo", "group": "itps", "prev_quarter": 0.12, "last_quarter": 0.22,
                      "status": "accelerating", "months": ["2026-02", "2026-05", "2026-08"]}],
  "ecosystem_quarterly_pace": {"prev_quarter": 0.195, "last_quarter": 0.177, "status": "stable", "months": ["…"]},
  "filters_label": "",
  "catalog": null,
  "unavailable": []
}
```

Regras:

- `null` = sem dado (nunca 0). Mensal = último valor de cada entidade no mês; semanal = a semana.
- `shares` = valor ÷ soma de todas as entidades no mesmo ponto. Com `granularity=week`, `group_share` continua mensal.
- `metric=api`: valores em 30 dias pelas últimas 4 semanas (mesma regra da aba 4); crescimento pelas médias de 4 semanas (aba 1).
- `headline.ecosystem_growth` e `growth` usam as mesmas regras da aba 1. `pp` vem em pontos percentuais.
- Participação no início e no fim: foto da semana; lacuna de até 3 semanas usa a observação anterior. Quem estreou depois do início parte de 0 e leva `debut_month`.
- `share_changes`: até 5 ganhos (maior primeiro) e até 5 perdas (a maior por último), só nos grupos escolhidos.
- `quarterly_pace`: 10 maiores no fim (nos grupos escolhidos). Fim de mês de m−6, m−3 e m. `status` "stable" quando |diferença| ≤ 3 pontos. Sem base em algum ponto → fica de fora.
- `catalog`: lista de transmissores (para "+ Adicionar") só com `by=transmitter`.
- Erros 422:
  - mais de 8 instituições;
  - `by=transmitter` sem `metric=active`;
  - `granularity` inválida;
  - `start` ≥ semana final.

---

## GET `/api/v2/changes`

| Parâmetro | Valores | Padrão |
|---|---|---|
| `month` | YYYY-MM | mês mais recente com dados |
| `types` | `decrease,increase,oscillation,new_entrant` | todos |
| `signal` | `consents`, `api`, `all` | `all` |
| `institution` | texto (contém, sem acento/caixa) | vazio |

```json
{
  "month": "2026-08",
  "months": [{"month": "2025-09", "decrease": 6, "increase": 4, "new_entrant": 0}, "..."],
  "summary": {"alerts": 12, "institutions": 6, "watching": 1,
              "by_kind": {"decrease": 9, "oscillation": 1, "new_entrant": 1}},
  "events": [{"uuid": "…", "name": "Banco Inter", "group": "neo_banks", "kind": "decrease",
              "max_abs_change": 0.81, "streak_months": 1,
              "items": [{"week": "2026-08-07", "metric": "api_group", "api_group": "Identidade",
                         "api_group_label": "Cadastro", "value_prev": 2218717.5,
                         "value_curr": 405461.5, "change_pct": -0.81}],
              "previous_month_summary": null}],
  "watching": [{"name": "Santander", "api_group_label": "Investimentos", "value_prev": 116200000,
                "value_curr": 68200000, "change_pct": -0.44, "confirm_week": "2026-09-04"}],
  "by_group": [{"group": "outros", "alerts": 4, "institutions": 3}],
  "rules": [{"title": "Consentimentos", "text": "…"}],
  "computed_at": "2026-09-23T…"
}
```

Regras: `summary.alerts` conta alertas (oscilação = 2), `by_kind` conta eventos; mês sem alertas → `events: []` e `months` preenchido.

---

## GET `/api/v2/institution/{uuid}`

| Parâmetro | Valores | Padrão |
|---|---|---|
| `compare` | `ecosystem`, `group`, ou UUID de outra instituição | `ecosystem` |

```json
{
  "institution": {"uuid": "…", "name": "Nubank", "group": "neo_banks",
                  "ranks": {"unique_pf": 1, "unique_pj": 2, "active": 1, "api": 1}},
  "compare": {"kind": "ecosystem", "label": "Ecossistema"},
  "kpis": {
    "unique_pf": {"value": 22044862, "share": 0.151, "growth": {"kind": "pct", "value": 0.49}},
    "unique_pj": {"…": "…"}, "active": {"…": "…"},
    "api": {"value": 4509500000, "share": 0.318, "per_consent_month": 866, "ref_per_consent_month": 443,
            "growth": {"kind": "pct", "value": 0.69}}
  },
  "evolution": {"points": ["2025-08", "…"], "values": [], "shares": []},
  "api_mix": [{"api_group": "Credito", "label": "Empréstimos", "share": 0.238, "ref_share": 0.163}],
  "api_by_group": [{"api_group": "Conta", "label": "Contas", "color": "#4A9EFF",
                    "monthly": [1052400000, "…"], "from": 1052400000, "to": 1428900000,
                    "growth": {"kind": "pct", "value": 0.36}}],
  "transmitters": [{"name": "Mercado Pago", "group": "neo_banks", "value": 7373581, "share": 0.196}],
  "error_rate": {"current": 0.023, "ref_current": 0.0472,
                 "series": [{"point": "2025-08", "value": 0.0404, "ref": 0.0419}],
                 "by_transmitter": [{"name": "Banco do Brasil", "value": 0.066}]},
  "alerts": {"last_12m": [], "last_alert": {"week": "2024-05-17", "groups": ["Cartao", "Credito", "Identidade"]}}
}
```

Regras: `api_mix` exclui `Resource`; `kpis.api` inclui todos os grupos; UUID inexistente → 404 com mensagem legível.
