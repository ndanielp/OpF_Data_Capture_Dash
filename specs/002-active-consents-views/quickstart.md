# Quickstart: Desenvolvendo as Visões de Consentimentos Ativos

**Feature**: `002-active-consents-views`
**Branch**: `002-active-consents-views`

---

## Pré-requisitos

1. Branch `001-active-consents` já mergeada em `main` (a tabela `active_consents` precisa existir no DB)
2. Pelo menos 1 coleta com `python main.py run --phase active-consents` executada localmente

Verificar se a tabela tem dados:
```bash
cd data-loader
python -c "
import sqlite3, config
con = sqlite3.connect(str(config.DB_PATH))
n = con.execute('SELECT COUNT(*) FROM active_consents').fetchone()[0]
dates = con.execute('SELECT DISTINCT date FROM active_consents ORDER BY date DESC LIMIT 3').fetchall()
print(f'{n} rows — últimas datas: {[d[0] for d in dates]}')
con.close()
"
```

---

## Estrutura de arquivos a criar

```
dashboard/
├── routers/
│   └── active_consents.py       # NOVO — 4 endpoints
├── gui/
│   └── active_consents.html     # NOVO — página de visões
└── server.py                    # MODIFICAR — registrar router + nova rota HTML + índices

tests/
└── test_active_consents_api.py  # NOVO — testes HTTP-level
```

---

## Passo 1 — Criar `dashboard/routers/active_consents.py`

Implementar 4 endpoints seguindo o contrato em `contracts/api-active-consents.md`:
- `GET /evolution` — série temporal por receptor ou transmissor
- `GET /matrix` — heatmap da semana mais recente
- `GET /ranking` — top-10 + Δ%
- `GET /intensity` — intensidade de uso (ativos ÷ únicos)

Padrões a seguir de `server.py`:
- `_db_con()` para abrir conexão SQLite (importado ou copiado)
- `_parse_date()` para parsing de datas
- `_parse_receptors()` para filtro de receptor
- `_build_color_map()` para cores de séries por instituição

Cabeçalho mínimo do router:
```python
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import sqlite3
from typing import Optional
from datetime import date, timedelta

router = APIRouter()
```

---

## Passo 2 — Modificar `dashboard/server.py`

### 2a. Registrar o novo router
```python
from routers import active_consents as active_consents_router
app.include_router(active_consents_router.router, prefix="/api/active-consents")
```

### 2b. Nova rota HTML
```python
@app.get("/active-consents", response_class=HTMLResponse)
async def active_consents_page():
    return HTMLResponse((GUI_DIR / "active_consents.html").read_text(encoding="utf-8"))
```

### 2c. Função de índices e chamada no lifespan
```python
def _ensure_active_consents_indexes() -> None:
    try:
        con = _db_con()
        try:
            con.execute("PRAGMA busy_timeout = 3000")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_date_receptor "
                "ON active_consents(date, receptor_uuid)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_date_transmitter "
                "ON active_consents(date, transmitter_uuid)"
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass
```

No `lifespan`, adicionar após `_ensure_dashboard_indexes()`:
```python
_ensure_active_consents_indexes()
```

---

## Passo 3 — Criar `dashboard/gui/active_consents.html`

### Layout mínimo
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Consentimentos Ativos — Open Finance Brasil</title>
  <!-- reutilizar o mesmo CSS do dashboard.html -->
</head>
<body>
  <nav><!-- links para /, /profile, /active-consents --></nav>

  <!-- KPI cards: total ativos, Δ% semanal -->
  <section id="kpi-cards"></section>

  <!-- Gráfico de evolução (Chart.js line) -->
  <section>
    <canvas id="chart-evolution"></canvas>
  </section>

  <!-- Ranking top-10 receptor / transmissor -->
  <section id="ranking"></section>

  <!-- Matriz receptor × transmissor (HTML table) -->
  <section id="matrix-container">
    <div id="matrix-tooltip"></div>
    <div class="table-scroll-wrapper">
      <table id="matrix-table"></table>
    </div>
  </section>

  <!-- Intensidade de uso (barras horizontais) -->
  <canvas id="chart-intensity"></canvas>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    // lógica de fetch e render para cada seção
  </script>
</body>
</html>
```

### Heatmap (tabela HTML)
Função JavaScript para gerar cor de célula:
```javascript
function heatColor(value, maxValue) {
    if (value === 0 || maxValue === 0) return 'transparent';
    const ratio = value / maxValue;
    // Escala: branco → azul escuro
    const r = Math.round(255 * (1 - ratio * 0.8));
    const g = Math.round(255 * (1 - ratio * 0.8));
    const b = 255;
    return `rgb(${r},${g},${b})`;
}
```

---

## Passo 4 — Criar testes em `tests/test_active_consents_api.py`

```python
import pytest
import sqlite3
from httpx import AsyncClient, ASGITransport
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
# ajustar DB_PATH para apontar para fixture
import config
# ... setup de DB com dados de teste

import server
from server import app

@pytest.mark.asyncio
async def test_evolution_empty_period(tmp_path):
    """Retorna estrutura vazia quando não há dados no período."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/active-consents/evolution?start=2000-01-01&end=2000-01-07")
    assert r.status_code == 200
    assert r.json()["series"] == []

@pytest.mark.asyncio
async def test_ranking_with_data(tmp_path, db_with_active_consents):
    """Top-N retorna items ordenados por total decrescente."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/active-consents/ranking?by=receptor")
    assert r.status_code == 200
    items = r.json()["items"]
    totals = [i["total"] for i in items]
    assert totals == sorted(totals, reverse=True)
```

---

## Verificação manual (Constituição II)

Após implementar:

```bash
cd dashboard
uvicorn server:app --reload --port 8000
```

Checklist visual obrigatório:
- [ ] `/active-consents` carrega sem erros de console
- [ ] Gráfico de evolução renderiza séries com cores corretas
- [ ] Seletor "por receptor / por transmissor" alterna corretamente
- [ ] Matriz exibe células coloridas proporcionais ao valor
- [ ] Tooltip da matriz mostra receptor, transmissor e total
- [ ] Ranking exibe Δ% (ou "—" para semana sem anterior)
- [ ] Intensidade de uso exibe "—" quando `unique_total = 0`
- [ ] Filtro de período muda os dados de todas as seções
- [ ] Sem erro HTTP 500 em nenhuma condição

---

## SQL de validação pós-implementação

```sql
-- Verificar dados disponíveis para o heatmap
SELECT date, COUNT(*) as pairs, SUM(total) as total_ativos
FROM active_consents
GROUP BY date
ORDER BY date DESC
LIMIT 5;

-- Verificar pares com maior volume (candidatos ao heatmap)
SELECT receptor, transmitter, total, date
FROM active_consents
ORDER BY date DESC, total DESC
LIMIT 20;

-- Verificar intensidade de uso para a semana mais recente
SELECT a.receptor,
       SUM(a.total) as active_total,
       u.total as unique_total,
       ROUND(1.0 * SUM(a.total) / NULLIF(u.total, 0), 1) as intensity
FROM active_consents a
LEFT JOIN unique_consents u
       ON a.receptor_uuid = u.receptor_uuid
      AND a.date = (SELECT MAX(date) FROM active_consents)
WHERE a.date = (SELECT MAX(date) FROM active_consents)
GROUP BY a.receptor, a.receptor_uuid, u.total
ORDER BY intensity DESC NULLS LAST
LIMIT 10;
```
