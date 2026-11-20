# Contract: `/api/v2/payments/*`

Somente leitura, JSON, números como contagens por 30 dias (float). `NaN` vira `null`. Sem a tabela `payment_weekly`, toda rota responde 200 com `"unavailable": ["payments"]` e listas vazias. Parâmetro inválido → 422 com `detail` em português. Uuid desconhecido → 404.

Siglas: `role` ∈ `ini` (iniciadora) | `det` (detentora). `api` ∈ `all` | `payments` | `automatic-payments`.

## GET /meta

```json
{
  "data_through": "2026-10-30",
  "months": ["2026-01", "…", "2026-10"],
  "apis": [{"slug": "payments", "label": "Iniciação de Pagamento", "short": "Inic.", "endpoint": 65,
            "color": "#1F4FD1", "line": "#1F4FD1", "color_dark": "#7B9BFF", "line_dark": "#7B9BFF"}, "…"],
  "heat": {"volume": "#1A3F9E", "fail": "#C2410C"},
  "institutions": [{"uuid": "…", "name": "NUBANK", "short": "Nubank", "group": "neo_banks", "roles": ["ini", "det"], "in_data": true}],
  "unavailable": []
}
```

`in_data` = a instituição também existe no tema Dados (link "ver no tema Dados").

## GET /ranking?role=ini&api=all&limit=10&pinned=a,b&excluded=c

```json
{
  "week": "2026-10-30", "window": {"start": "2026-10-09", "end": "2026-10-30"},
  "role": "ini", "api": "all",
  "ecosystem": {"total": 62.2e6, "initiators": 42, "holders": 68,
                "payments": {"value": 16.4e6, "share": 0.26, "fail": 0.032},
                "automatic-payments": {"value": 45.9e6, "share": 0.74, "fail": 0.421},
                "ip_share_prev": 0.35},
  "rows": [{"uuid": "…", "name": "Iniciador", "group": "itps", "pinned": false, "cut": false,
            "payments": 1.99e6, "automatic-payments": 31.4e6, "value": 33.4e6, "share": 0.536,
            "fail": {"payments": 0.006, "automatic-payments": 0.507}, "growth": 0.35}],
  "excluded": [{"uuid": "…", "name": "…"}],
  "unavailable": []
}
```

`value` e `share` seguem o filtro `api`; `share` = valor ÷ total da API escolhida. `growth` = janela atual ÷ anterior − 1 (`null` sem base). Fixadas fora do Top `limit` vêm ao fim com `cut: true` na primeira delas. `limit` 1–50.

## GET /flows?size=8

```json
{
  "months": ["2026-01", "…"], "week": "2026-10-30",
  "rows": [{"uuid": "…", "name": "Iniciador"}, "…", {"uuid": null, "name": "Outras iniciadoras"}],
  "cols": [{"uuid": "…", "name": "Itaú"}, "…", {"uuid": null, "name": "Outras detentoras"}],
  "data": {"payments": {"2026-01": {"ok": [[…]], "fail": [[…]]}}, "automatic-payments": {"…": "…"}},
  "unavailable": []
}
```

`ok[i][j]` = transações por 30 dias da linha i com a coluna j no mês. `size` 2–12.

## GET /enrollment?receptor=&transmitter=

Sem filtros = ecossistema; `transmitter=uuid` = vínculos com contas da detentora; `receptor=uuid` = vínculos iniciados pela iniciadora.

```json
{
  "window": {"start": "…", "end": "…"},
  "steps": [{"endpoint": 133, "label": "Vínculo iniciado", "value": 1581617.0}, {"endpoint": 139, "…": "…"},
            {"endpoint": 136, "…": "…"}, {"endpoint": 137, "…": "…"}],
  "ended": 145000.0, "conversion": 0.47, "authorization": 0.51,
  "monthly": [{"month": "2026-01", "conversion": 0.426}, "…"],
  "unavailable": []
}
```

`conversion`/`authorization` `null` sem denominador. Os dois filtros juntos → 422.

## GET /changes

```json
{
  "week": "2026-10-30", "month": "2026-10",
  "window": {"start": "2026-10-09", "end": "2026-10-30", "prev_start": "2026-09-11", "prev_end": "2026-10-02"},
  "floor": {"transactions": 30000, "enrollments": 1000},
  "alerts": [{"uuid": "…", "name": "Banco Inter", "role": "det", "kind": "fail", "api": "automatic-payments",
              "direction": "up", "before": 0.419, "after": 0.647, "change": 0.228}],
  "watching": ["mesma forma"],
  "unavailable": []
}
```

`change`: volume = razão − 1; falha e conversão = diferença de taxas (fração; 0,05 = 5 pp). Ordem: maior |change| primeiro dentro de cada tipo, tipos na ordem falha, volume, conversão.

## GET /institution/{uuid}?role=det

```json
{
  "institution": {"uuid": "…", "name": "NUBANK", "short": "Nubank", "group": "neo_banks", "in_data": true},
  "role": "det", "roles": ["ini", "det"], "months": ["…"], "week": "2026-10-30",
  "counterparts": [{"uuid": "…", "name": "Google Pay"}, "…", {"uuid": null, "name": "Outras iniciadoras"}],
  "data": {"payments": {"2026-10": {"ok": [per counterpart], "fail": [per counterpart]}}, "automatic-payments": {"…": "…"}},
  "ecosystem": {"payments": {"2026-10": {"ok": 1.6e7, "fail": 5.2e5}}, "automatic-payments": {"…": "…"}},
  "rank": {"position": 4, "of": 68},
  "polls": {"payments": 2.8, "automatic-payments": 1.5},
  "enrollment": {"…": "mesma forma de /enrollment, do papel"}, "enrollment_ecosystem": {"conversion": 0.47, "authorization": 0.51},
  "unavailable": []
}
```

`role` omitido = papel de maior volume nas últimas 4 semanas; `role` sem dados → usa o outro e informa em `role`. Contrapartes = 8 maiores do papel pelas últimas 4 semanas + "Outras". `rank` = posição no último mês entre todas do papel. `polls` `null` sem criação. `enrollment` = `null` quando a instituição não tem vínculo iniciado no papel.
