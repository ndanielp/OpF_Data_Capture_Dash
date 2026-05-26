# API Contract: Active Consents Dashboard Endpoints

**Feature**: `002-active-consents-views`
**Prefix**: `/api/active-consents`
**Router**: `dashboard/routers/active_consents.py`

---

## Parâmetros comuns

| Parâmetro   | Tipo   | Default          | Descrição                                                     |
|-------------|--------|------------------|---------------------------------------------------------------|
| `start`     | string | 52 semanas atrás | Data início do período (YYYY-MM-DD)                           |
| `end`       | string | hoje             | Data fim do período (YYYY-MM-DD)                              |
| `receptors` | string | `null`           | Nomes de receptores separados por vírgula (substring match)   |

---

## GET `/api/active-consents/evolution`

Retorna série temporal de consentimentos ativos, agrupada por receptor ou transmissor.

### Query Parameters

| Parâmetro | Tipo   | Default    | Valores aceitos            |
|-----------|--------|------------|----------------------------|
| `start`   | string | 52w atrás  | YYYY-MM-DD                 |
| `end`     | string | hoje       | YYYY-MM-DD                 |
| `by`      | string | `receptor` | `receptor`, `transmitter`  |
| `receptors` | string | `null`   | nomes separados por vírgula |

### Response

```json
{
  "labels": ["2026-01-06", "2026-01-13", "..."],
  "series": [
    {
      "name": "Banco Bradesco S.A.",
      "color": "#E8192C",
      "values": [12500, 12800, 13100, "..."]
    }
  ],
  "by": "receptor"
}
```

| Campo            | Tipo           | Descrição                                                     |
|------------------|----------------|---------------------------------------------------------------|
| `labels`         | string[]       | Datas das semanas no período (YYYY-MM-DD)                     |
| `series[].name`  | string         | Nome do receptor ou transmissor                               |
| `series[].color` | string         | Cor hex (de `_build_color_map()`)                             |
| `series[].values`| (int\|null)[]  | Total de ativos por semana; `null` se sem dado naquela semana |
| `by`             | string         | Dimensão de agrupamento usada                                 |

**Quando sem dados**: `{"labels": [], "series": [], "by": "receptor"}`

---

## GET `/api/active-consents/matrix`

Retorna a matriz receptor × transmissor para a semana mais recente no período.

### Query Parameters

| Parâmetro   | Tipo   | Default   | Descrição                           |
|-------------|--------|-----------|-------------------------------------|
| `end`       | string | hoje      | Semana de referência (max disponível ≤ end) |
| `receptors` | string | `null`    | Filtro de receptor (substring match) |

### Response

```json
{
  "receptors": ["Bradesco", "Itaú", "..."],
  "transmitters": ["Bradesco", "99Pay", "..."],
  "values": [[1200, 0, 340], [890, 120, 0]],
  "reference_date": "2026-05-19",
  "max_value": 1200
}
```

| Campo             | Tipo       | Descrição                                                      |
|-------------------|------------|----------------------------------------------------------------|
| `receptors`       | string[]   | Nomes dos receptores (linhas da matriz)                        |
| `transmitters`    | string[]   | Nomes dos transmissores (colunas da matriz)                    |
| `values`          | int[][]    | `values[i][j]` = total do par `receptors[i] × transmitters[j]` |
| `reference_date`  | string     | Data usada (semana mais recente ≤ end)                         |
| `max_value`       | int        | Valor máximo na matriz (para escala de cor)                    |

**Quando sem dados**: `{"receptors": [], "transmitters": [], "values": [], "reference_date": null, "max_value": 0}`

---

## GET `/api/active-consents/ranking`

Retorna ranking top-10 de receptores ou transmissores por volume de ativos, com Δ%.

### Query Parameters

| Parâmetro   | Tipo   | Default    | Valores aceitos           |
|-------------|--------|------------|---------------------------|
| `end`       | string | hoje       | YYYY-MM-DD                |
| `by`        | string | `receptor` | `receptor`, `transmitter` |
| `limit`     | int    | `10`       | 1–50                      |

### Response

```json
{
  "items": [
    {
      "name": "Banco Bradesco S.A.",
      "total": 45200,
      "total_prev": 43800,
      "delta_pct": 3.2,
      "color": "#E8192C"
    }
  ],
  "reference_date": "2026-05-19",
  "prev_date": "2026-05-12",
  "by": "receptor"
}
```

| Campo               | Tipo         | Descrição                                           |
|---------------------|--------------|-----------------------------------------------------|
| `items[].name`      | string       | Nome do receptor ou transmissor                     |
| `items[].total`     | int          | Total de ativos na semana de referência             |
| `items[].total_prev`| int \| null  | Total na semana anterior; `null` se não disponível  |
| `items[].delta_pct` | float \| null| Variação % vs semana anterior; `null` se N/D        |
| `items[].color`     | string       | Cor hex                                             |
| `reference_date`    | string       | Semana mais recente usada                           |
| `prev_date`         | string\|null | Semana anterior usada para Δ%; `null` se não existe |
| `by`                | string       | Dimensão de agrupamento usada                       |

**Quando sem dados**: `{"items": [], "reference_date": null, "prev_date": null, "by": "receptor"}`

---

## GET `/api/active-consents/intensity`

Retorna intensidade de uso por receptor (ativos ÷ únicos) para a semana mais recente.

### Query Parameters

| Parâmetro   | Tipo   | Default | Descrição                          |
|-------------|--------|---------|------------------------------------|
| `end`       | string | hoje    | Semana de referência (max ≤ end)   |
| `receptors` | string | `null`  | Filtro de receptor (substring)     |

### Response

```json
{
  "items": [
    {
      "receptor": "Banco Bradesco S.A.",
      "active_total": 45200,
      "unique_total": 22100,
      "intensity": 2.0,
      "color": "#E8192C"
    }
  ],
  "reference_date": "2026-05-19"
}
```

| Campo              | Tipo         | Descrição                                                        |
|--------------------|--------------|------------------------------------------------------------------|
| `items[].receptor` | string       | Nome do receptor                                                 |
| `items[].active_total` | int      | Total de consentimentos ativos (soma dos transmissores)          |
| `items[].unique_total` | int\|null| Clientes únicos (`unique_consents.total`); `null` se não existe  |
| `items[].intensity`| float\|null  | `active_total / unique_total`; `null` se denominador 0 ou null  |
| `items[].color`    | string       | Cor hex                                                          |
| `reference_date`   | string\|null | Semana mais recente usada; `null` se sem dados                   |

**Quando sem dados**: `{"items": [], "reference_date": null}`

---

## Rota HTML

```
GET /active-consents  →  dashboard/gui/active_consents.html
```

Registrada em `server.py`:
```python
@app.get("/active-consents", response_class=HTMLResponse)
async def active_consents_page():
    return HTMLResponse((GUI_DIR / "active_consents.html").read_text(encoding="utf-8"))
```

---

## Testes esperados (Constituição II)

Para cada endpoint acima, `tests/test_active_consents_api.py` deve cobrir:
1. Happy path com dados (status 200, shape do JSON correto)
2. Período sem dados (retorna estrutura vazia, não HTTP 404/500)
3. Filtro de receptor aplicado corretamente

Framework: `httpx.AsyncClient` contra a app FastAPI (padrão existente).
