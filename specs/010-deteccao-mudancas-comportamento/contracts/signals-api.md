# Contract: `GET /api/signals`

Router novo `dashboard/routers/signals.py`, montado em `/api/signals` em `server.py`
(mesmo padrão do `active_consents`). Somente leitura.

## Query params

| Param | Tipo | Padrão | Semântica |
|---|---|---|---|
| `week` | `YYYY-MM-DD` | semana mais recente com dado | Semana exibida. Semana inexistente → resposta vazia com `weeks` preenchido, não erro. |
| `groups` | slugs separados por vírgula | nenhum | Mesmo parâmetro e semântica dos endpoints da 009: união entre grupos de instituição; slug desconhecido é ignorado. Resolvido por `resolve_institution_group(receptor)`. |

## Response 200

```json
{
  "week": "2026-08-28",
  "weeks": [
    {"week": "2026-08-28", "count": 3},
    {"week": "2026-08-21", "count": 5}
  ],
  "sections": {
    "new_entrant": [
      {
        "receptor": "BANCO AGIBANK",
        "institution_group": "outros",
        "volume": 64572,
        "items": [
          {"metric": "unique_consents", "api_group": null,
           "value_prev": null, "value_curr": 31481, "change_pct": null}
        ]
      }
    ],
    "increase": [],
    "decrease": [
      {
        "receptor": "BANCO SAFRA",
        "institution_group": "outros",
        "volume": 26427,
        "items": [
          {"metric": "api_group", "api_group": "Cartao", "value_prev": 2100000,
           "value_curr": 810000, "change_pct": -0.61},
          {"metric": "api_group", "api_group": "Credito", "value_prev": 1900000,
           "value_curr": 820000, "change_pct": -0.57}
        ]
      }
    ]
  },
  "api_incomplete": false,
  "computed_at": "2026-09-23T11:10:05Z",
  "consents_through": "2026-08-28",
  "api_through": "2026-08-28"
}
```

*(valores ilustrativos)*

- `weeks`: todas as semanas com pelo menos um alerta **depois do filtro de grupos**,
  mais recentes primeiro — alimenta o seletor de semana.
- `sections`: sempre as três chaves, na ordem da spec. Em cada seção, **uma entrada por
  instituição** com seus alertas em `items`, ordenadas por `volume` decrescente.
- `api_incomplete`: `true` quando `week` está em `api_skipped_weeks` — o card mostra o aviso.
- `api_group`: slug de `API_GROUPS`; o frontend usa o `display` de `/api/of/api-groups`.

## Tabela ainda não criada

Base sem `behavior_signals` (ex.: base na nuvem antes da primeira execução do script):
resposta 200 com `sections` vazias, `weeks: []` e `computed_at: null`. O dashboard **não
cria** a tabela (Princípio V) — só trata a ausência.

## Erros

| Situação | Resposta |
|---|---|
| `week` com formato inválido | tratado como ausente (semana mais recente), como `_parse_date` nos demais endpoints |
| erro de SQLite | 200 com estrutura vazia, mesmo padrão do `active_consents.py` |
