# PRD Técnico v1 — Tab Perfil de Receptor
> **Para agente de código (Claude Code / Gemini CLI)**
> Este documento é a fonte única de verdade para implementação. Siga as especificações exatamente. Não invente decisões — tudo que não está aqui deve gerar uma dúvida explícita antes de qualquer código.

---

## 0. Contexto e ponto de partida

| Item | Detalhe |
|---|---|
| Repositório / projeto | FastAPI existente (adicionar router; não criar novo projeto) |
| Banco de dados | SQLite — path configurável via `OF_DB_PATH` (env var) |
| Banco de protótipo | `consents - Filtrado.db` (7 receptores, Jun/2025–Mar/2026) |
| Frontend existente | `bradesco_receptor_profile.html` — será adaptado para consumir a API |
| Objetivo desta v1 | Substituir todos os dados hardcoded do HTML por chamadas à API REST |

---

## 1. Escopo da v1

### Inclui
- Três endpoints REST novos (ver Seção 4)
- Adaptação do `bradesco_receptor_profile.html` para consumir esses endpoints
- Seletor dinâmico de instituição (substituir Bradesco fixo)
- Benchmarks calculados dinamicamente pelo backend (substituir `EP_STATS` hardcoded)
- Cache em memória com TTL de 1 hora

### Não inclui (explicitamente fora de escopo)
- Autenticação / login
- Filtro de período interativo (os endpoints aceitam `from`/`to` mas o frontend usa período completo por padrão)
- Exportação PDF/Excel
- Comparação lado-a-lado de duas instituições
- Dados de transmissores
- Migração para outro banco (PostgreSQL, BigQuery)

---

## 2. Estrutura de arquivos a criar/modificar

```
projeto/
├── app/
│   ├── main.py                  # existente — adicionar include_router
│   └── routers/
│       └── openfinance.py       # NOVO — todos os endpoints desta feature
├── app/services/
│   └── of_analytics.py          # NOVO — lógica de negócio e queries SQL
├── app/cache.py                 # NOVO (ou existente) — TTLCache wrapper
├── static/
│   └── bradesco_receptor_profile.html  # MODIFICAR — substituir dados hardcoded
├── .env                         # adicionar OF_DB_PATH
└── requirements.txt             # adicionar: cachetools
```

> Se `app/services/` não existir, criar o diretório com `__init__.py` vazio.

---

## 3. Configuração

### Variáveis de ambiente (`.env`)
```
OF_DB_PATH=/caminho/absoluto/para/consents - Filtrado.db
OF_CACHE_TTL_SECONDS=3600
```

### Dependências a adicionar em `requirements.txt`
```
cachetools>=5.3.0
```

### Leitura da configuração em `openfinance.py`
```python
import os
DB_PATH = os.environ.get("OF_DB_PATH", "consents - Filtrado.db")
CACHE_TTL = int(os.environ.get("OF_CACHE_TTL_SECONDS", 3600))
```

---

## 4. Endpoints REST

Prefixo do router: `/api/of`
Registrar em `main.py`:
```python
from app.routers.openfinance import router as of_router
app.include_router(of_router, prefix="/api/of")
```

### 4.1 `GET /api/of/institutions`

Retorna a lista de receptores disponíveis no banco.

**Response 200**
```json
{
  "institutions": [
    {
      "id": "BRADESCO",
      "label": "Bradesco",
      "uuid": "a72a6d4f-79be-5362-afb6-f8d9c9c39cf5"
    }
  ]
}
```

**SQL**
```sql
SELECT DISTINCT receptor AS id, receptor_uuid AS uuid
FROM unique_consents
ORDER BY receptor
```

**Label formatting** — aplicar `title()` com exceções:
```python
LABEL_MAP = {
    "ITAÚ UNIBANCO": "Itaú Unibanco",
    "CAIXA ECONOMICA FEDERAL": "Caixa Econômica Federal",
    "BANCO DO BRASIL": "Banco do Brasil",
    "MERCADO PAGO": "Mercado Pago",
    "SANTANDER BRASIL": "Santander Brasil",
    "BRADESCO": "Bradesco",
    "NUBANK": "Nubank",
}
label = LABEL_MAP.get(row["id"], row["id"].title())
```

**Cache:** resultado cacheado por `CACHE_TTL` segundos (chave `"institutions"`).

---

### 4.2 `GET /api/of/ecosystem-stats`

Retorna mediana e 3º quartil por endpoint, calculados sobre todos os receptores disponíveis.

**Query params:** nenhum  
**Response 200**
```json
{
  "stats": {
    "accounts|||Saldos da Conta": { "median": 47.39, "q3": 68.40 },
    "customers|||Identificação pessoa natural": { "median": 1.10, "q3": 2.27 }
  },
  "receptor_count": 7,
  "computed_at": "2026-04-15T10:30:00Z"
}
```

**Chave:** `"{api}|||{endpoint}"` — mesmo formato do protótipo.

**Lógica de cálculo (implementar em `of_analytics.py`):**

```python
import sqlite3, statistics

def get_ecosystem_stats(db_path: str) -> dict:
    """
    Para cada (api, endpoint), calcula a intensidade média de cada receptor
    no período completo disponível, depois computa mediana e Q3 entre receptores.
    Exclui: api IN ('consents', 'resources') e status != 200.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1. Buscar todas as semanas disponíveis por receptor
    cur.execute("""
        SELECT r.date, r.receptor, r.api, r.endpoint,
               SUM(r.total) AS req_week,
               c.cpf, c.cnpj, c.total AS consents_total
        FROM api_requests r
        JOIN unique_consents c
          ON r.date = c.date AND r.receptor = c.receptor
        WHERE r.api NOT IN ('consents', 'resources')
          AND r.status = 200
        GROUP BY r.date, r.receptor, r.api, r.endpoint
    """)
    rows = cur.fetchall()
    con.close()

    # 2. Agrupar por (receptor, api, endpoint) → lista de intensidades semanais
    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(list))
    for row in rows:
        consents = _get_consents(row)
        if consents <= 0:
            continue
        intensity = (row["req_week"] / consents) * (30 / 7)
        key = f"{row['api']}|||{row['endpoint']}"
        data[key][row["receptor"]].append(intensity)

    # 3. Para cada (api, endpoint), calcular média por receptor, depois mediana/Q3
    stats = {}
    for key, receptor_weeks in data.items():
        receptor_means = [
            sum(weeks) / len(weeks)
            for weeks in receptor_weeks.values()
            if len(weeks) > 0
        ]
        if len(receptor_means) < 2:
            continue
        receptor_means_sorted = sorted(receptor_means)
        n = len(receptor_means_sorted)
        median = statistics.median(receptor_means_sorted)
        upper_half = receptor_means_sorted[n - n // 2:]
        q3 = statistics.median(upper_half)
        stats[key] = {"median": round(median, 4), "q3": round(q3, 4)}

    return stats

def _get_consents(row) -> float:
    """
    PJ endpoints usam cnpj; PF endpoints usam cpf; demais usam total.
    """
    ep = row["endpoint"].lower()
    if "jurídica" in ep or "juridica" in ep:
        return float(row["cnpj"] or 0)
    if "natural" in ep:
        return float(row["cpf"] or 0)
    return float(row["consents_total"] or 0)
```

**Cache:** resultado cacheado por `CACHE_TTL` (chave `"ecosystem_stats"`).

---

### 4.3 `GET /api/of/receptor-profile`

Retorna o perfil completo de uma instituição para renderização do dashboard.

**Query params:**
| Param | Tipo | Obrigatório | Default | Validação |
|---|---|---|---|---|
| `institution` | string | Sim | — | Deve existir em `unique_consents.receptor`; retornar 404 se não encontrado |
| `from` | string (YYYY-MM-DD) | Não | data mínima do banco | ISO 8601 |
| `to` | string (YYYY-MM-DD) | Não | data máxima do banco | ISO 8601 |

**Response 200 — estrutura completa:**
```json
{
  "institution": {
    "id": "BRADESCO",
    "label": "Bradesco",
    "uuid": "a72a6d4f-79be-5362-afb6-f8d9c9c39cf5",
    "archetype": "Crédito & Cartões",
    "archetype_description": "Consumo concentrado em crédito, cartões e financiamentos, com uso relevante de conta corrente."
  },
  "summary": {
    "total_consents": 1234567,
    "active_apis": 8,
    "top_category": "credit-cards-accounts",
    "weeks_count": 39
  },
  "mix_data": [
    {
      "date": "2025-06-06",
      "accounts": 12.3,
      "credit_cards_accounts": 45.6,
      "customers": 2.1,
      "loans": 8.9,
      "financings": 0.0,
      "invoice_financings": 0.0,
      "unarranged_accounts_overdraft": 0.0,
      "bank_fixed_incomes": 0.0,
      "credit_fixed_incomes": 0.0,
      "variable_incomes": 0.0,
      "funds": 0.0,
      "treasure_titles": 0.0,
      "exchanges": 0.0
    }
  ],
  "tornado_data": [
    { "category": "accounts", "label": "Conta", "institution_share": 0.18, "ecosystem_share": 0.22 }
  ],
  "endpoint_data": {
    "Conta": {
      "color": "#4A90D9",
      "apis": {
        "accounts": {
          "label": "Contas",
          "endpoints": {
            "Saldos da Conta": 47.2,
            "Limites da Conta": 22.1
          }
        },
        "credit-cards-accounts": {
          "label": "Cartão de Crédito",
          "endpoints": {
            "Identificação de Conta de Pagamento Pós-Paga": 12.3
          }
        }
      }
    }
  },
  "period": {
    "from": "2025-06-06",
    "to": "2026-03-06",
    "weeks_count": 39
  }
}
```

**Response 404**
```json
{ "detail": "Institution 'XYZ' not found" }
```

---

## 5. Lógica de negócio (`of_analytics.py`)

### 5.1 Agrupamento de APIs em categorias

```python
API_GROUPS = {
    "Conta": {
        "color": "#4A90D9",
        "apis": ["accounts", "credit-cards-accounts"],
    },
    "Crédito": {
        "color": "#E8734A",
        "apis": ["loans", "financings", "invoice-financings", "unarranged-accounts-overdraft"],
    },
    "Investimentos": {
        "color": "#7B68EE",
        "apis": ["bank-fixed-incomes", "credit-fixed-incomes", "variable-incomes", "funds", "treasure-titles"],
    },
    "Identidade": {
        "color": "#50C878",
        "apis": ["customers"],
    },
    "Câmbio": {
        "color": "#FFB347",
        "apis": ["exchanges"],
    },
}

API_LABELS = {
    "accounts": "Contas",
    "credit-cards-accounts": "Cartão de Crédito",
    "loans": "Empréstimos",
    "financings": "Financiamentos",
    "invoice-financings": "Financiamentos de Faturas",
    "unarranged-accounts-overdraft": "Cheque Especial",
    "bank-fixed-incomes": "Renda Fixa Bancária",
    "credit-fixed-incomes": "Renda Fixa Crédito",
    "variable-incomes": "Renda Variável",
    "funds": "Fundos",
    "treasure-titles": "Títulos do Tesouro",
    "customers": "Dados Cadastrais",
    "exchanges": "Câmbio",
}
```

### 5.2 Query principal do perfil

```sql
-- Intensidade semanal por endpoint para a instituição selecionada
SELECT
    r.date,
    r.api,
    r.endpoint,
    SUM(r.total)     AS req_week,
    c.cpf            AS consents_cpf,
    c.cnpj           AS consents_cnpj,
    c.total          AS consents_total
FROM api_requests r
JOIN unique_consents c
    ON r.date = c.date AND r.receptor = c.receptor
WHERE r.receptor = :receptor
  AND r.api NOT IN ('consents', 'resources')
  AND r.status = 200
  AND r.date >= :from_date
  AND r.date <= :to_date
GROUP BY r.date, r.api, r.endpoint
ORDER BY r.date, r.api, r.endpoint
```

### 5.3 Normalização

```python
def normalize(req_week: float, consents: float, days: int = 30) -> float:
    """Converte req/semana em req/consent/N-dias."""
    if consents <= 0:
        return 0.0
    return (req_week / consents) * (days / 7)
```

### 5.4 Construção de `mix_data`

Para cada semana distinta no resultado:
1. Para cada API, somar `normalize(req_week, consents)` de todos os endpoints daquela API
2. Retornar dict `{ date, api_slug_1: valor, api_slug_2: valor, ... }`
3. Slug = API name com hífens substituídos por underscore (ex: `credit-cards-accounts` → `credit_cards_accounts`)

### 5.5 Construção de `tornado_data`

Para cada categoria de `API_GROUPS`:
1. Calcular total de requisições da instituição nessa categoria no período completo
2. Calcular total de requisições de todos os receptores nessa categoria
3. `institution_share = categoria_inst / total_inst`
4. `ecosystem_share = categoria_ecossistema / total_ecossistema`

```sql
-- Total por API para a instituição
SELECT api, SUM(total) AS total
FROM api_requests
WHERE receptor = :receptor
  AND api NOT IN ('consents','resources')
  AND status = 200
  AND date >= :from_date AND date <= :to_date
GROUP BY api

-- Total por API para todo o ecossistema
SELECT api, SUM(total) AS total
FROM api_requests
WHERE api NOT IN ('consents','resources')
  AND status = 200
  AND date >= :from_date AND date <= :to_date
GROUP BY api
```

### 5.6 Construção de `endpoint_data`

Para cada grupo → API → endpoint:
- Calcular a **média** da intensidade semanal ao longo do período
- Estrutura conforme response schema da Seção 4.3

### 5.7 Classificação de arquetipo

```python
def classify_archetype(category_shares: dict[str, float]) -> tuple[str, str]:
    """
    Recebe dict {categoria: share_instituição}.
    Retorna (archetype_name, archetype_description).
    Regras (avaliadas em ordem — primeira que bater vence):
    """
    conta        = category_shares.get("Conta", 0)
    credito      = category_shares.get("Crédito", 0)
    invest       = category_shares.get("Investimentos", 0)
    identidade   = category_shares.get("Identidade", 0)
    cambio       = category_shares.get("Câmbio", 0)

    if credito > 0.45:
        return "Foco em Crédito", "Consumo dominado por APIs de crédito (empréstimos, financiamentos e cartões)."
    if invest > 0.40:
        return "Foco em Investimentos", "Consumo concentrado em APIs de renda fixa, variável e fundos."
    if conta > 0.50:
        return "Foco em Conta Corrente", "Consumo predominante de dados de conta (saldos, limites, extratos)."
    if credito > 0.30 and conta > 0.25:
        return "Crédito & Conta", "Mix equilibrado entre dados de conta e crédito."
    if invest > 0.25 and credito > 0.25:
        return "Crédito & Investimentos", "Combinação relevante de crédito e produtos de investimento."
    if identidade > 0.30:
        return "Foco em Identidade", "Alta proporção de consultas a dados cadastrais (PF e PJ)."
    return "Perfil Diversificado", "Consumo distribuído entre múltiplas categorias sem dominância clara."
```

### 5.8 Cálculo de `summary`

```python
summary = {
    "total_consents": # MAX(consents_total) do período para a instituição (última semana)
    "active_apis":    # COUNT(DISTINCT api) com total > 0 no período
    "top_category":   # categoria com maior share (da instituição)
    "weeks_count":    # COUNT(DISTINCT date) no resultado
}
```

---

## 6. Cache

Usar `cachetools.TTLCache`. Implementar em `app/cache.py`:

```python
from cachetools import TTLCache
import os

_cache: TTLCache = None

def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        ttl = int(os.environ.get("OF_CACHE_TTL_SECONDS", 3600))
        _cache = TTLCache(maxsize=128, ttl=ttl)
    return _cache
```

Uso no router:
```python
from app.cache import get_cache

@router.get("/ecosystem-stats")
def ecosystem_stats():
    cache = get_cache()
    if "ecosystem_stats" not in cache:
        cache["ecosystem_stats"] = of_analytics.get_ecosystem_stats(DB_PATH)
    return cache["ecosystem_stats"]
```

Chaves de cache:
| Chave | Endpoint | TTL |
|---|---|---|
| `"institutions"` | `/institutions` | `OF_CACHE_TTL_SECONDS` |
| `"ecosystem_stats"` | `/ecosystem-stats` | `OF_CACHE_TTL_SECONDS` |
| `"profile:{institution}:{from}:{to}"` | `/receptor-profile` | `OF_CACHE_TTL_SECONDS` |

---

## 7. Adaptações no frontend (`bradesco_receptor_profile.html`)

### 7.1 O que remover
- Todo o bloco `const EP_DATA = { ... }` (dados hardcoded de Bradesco)
- Todo o bloco `const EP_STATS = { ... }` (benchmarks hardcoded)
- Qualquer outra variável JS com dados hardcoded de uma instituição específica

### 7.2 Adicionar: Institution Selector

Inserir no topo do dashboard, antes do primeiro card:

```html
<div id="institution-selector" style="...">
  <label for="inst-search">Instituição</label>
  <input type="text" id="inst-search" placeholder="Buscar instituição..." autocomplete="off">
  <ul id="inst-dropdown" hidden></ul>
</div>
```

Comportamento:
1. No `DOMContentLoaded`, chamar `GET /api/of/institutions` e popular a lista
2. Ao selecionar, atualizar `?institution=` na URL (sem reload) via `history.replaceState`
3. Disparar `loadProfile(institutionId)`

### 7.3 Função `loadProfile(id)`

```javascript
async function loadProfile(institutionId) {
  showSkeletons(); // exibir placeholders em todos os charts

  const [profileRes, statsRes] = await Promise.all([
    fetch(`/api/of/receptor-profile?institution=${encodeURIComponent(institutionId)}`),
    fetch('/api/of/ecosystem-stats')
  ]);

  if (!profileRes.ok) { showError(profileRes.status); return; }

  const profile = await profileRes.json();
  const ecosystemStats = await statsRes.json();

  renderHeader(profile.institution);
  renderSummary(profile.summary);
  renderMixChart(profile.mix_data);
  renderTornadoChart(profile.tornado_data);
  renderEndpointSection(profile.endpoint_data, ecosystemStats.stats);
}
```

### 7.4 Persistência via URL

```javascript
// Ao carregar a página:
const params = new URLSearchParams(window.location.search);
const inst = params.get('institution') || 'BRADESCO';
loadProfile(inst);

// Ao trocar instituição:
history.replaceState(null, '', `?institution=${encodeURIComponent(id)}`);
```

### 7.5 Estados obrigatórios

| Estado | Trigger | Comportamento |
|---|---|---|
| Loading | `loadProfile()` chamado | Skeleton em cada chart (div com `background: #2a2a3e; border-radius: 4px; animation: pulse`) |
| Empty | Nenhuma instituição selecionada | Card central com ícone + "Selecione uma instituição acima para ver o perfil" |
| Error 404 | Instituição não encontrada | Toast/banner vermelho "Instituição não encontrada" |
| Error 500 | Falha de backend | Toast/banner "Erro ao carregar dados. Tente novamente." |

---

## 8. Tratamento de erros no backend

```python
from fastapi import HTTPException

# 404 — instituição não encontrada
raise HTTPException(status_code=404, detail=f"Institution '{institution}' not found")

# 500 — erro de banco
try:
    ...
except sqlite3.Error as e:
    raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

---

## 9. Cenários de teste

O agente deve implementar e rodar os testes abaixo antes de considerar a feature completa.

### 9.1 Testes de integração (pytest)

```python
# tests/test_of_endpoints.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_institutions_returns_list():
    r = client.get("/api/of/institutions")
    assert r.status_code == 200
    data = r.json()
    assert "institutions" in data
    assert len(data["institutions"]) >= 1
    assert all("id" in i and "label" in i for i in data["institutions"])

def test_institutions_includes_bradesco():
    r = client.get("/api/of/institutions")
    ids = [i["id"] for i in r.json()["institutions"]]
    assert "BRADESCO" in ids

def test_ecosystem_stats_has_expected_keys():
    r = client.get("/api/of/ecosystem-stats")
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    # Verificar que pelo menos um endpoint de accounts existe
    keys = list(data["stats"].keys())
    assert any("accounts" in k for k in keys)

def test_ecosystem_stats_values_are_positive():
    r = client.get("/api/of/ecosystem-stats")
    for key, val in r.json()["stats"].items():
        assert val["median"] >= 0, f"Negative median for {key}"
        assert val["q3"] >= val["median"], f"Q3 < median for {key}"

def test_receptor_profile_bradesco():
    r = client.get("/api/of/receptor-profile?institution=BRADESCO")
    assert r.status_code == 200
    data = r.json()
    assert data["institution"]["id"] == "BRADESCO"
    assert len(data["mix_data"]) > 0
    assert len(data["tornado_data"]) > 0
    assert "endpoint_data" in data

def test_receptor_profile_not_found():
    r = client.get("/api/of/receptor-profile?institution=INEXISTENTE")
    assert r.status_code == 404

def test_receptor_profile_all_institutions():
    institutions = client.get("/api/of/institutions").json()["institutions"]
    for inst in institutions:
        r = client.get(f"/api/of/receptor-profile?institution={inst['id']}")
        assert r.status_code == 200, f"Failed for {inst['id']}"

def test_receptor_profile_with_date_filter():
    r = client.get("/api/of/receptor-profile?institution=BRADESCO&from=2025-10-01&to=2026-01-31")
    assert r.status_code == 200
    data = r.json()
    # Verificar que datas fora do intervalo não aparecem no mix_data
    for week in data["mix_data"]:
        assert "2025-10-01" <= week["date"] <= "2026-01-31"

def test_intensity_normalization_is_reasonable():
    """Intensidade média não deve ser negativa nem absurdamente alta."""
    r = client.get("/api/of/receptor-profile?institution=BRADESCO")
    ed = r.json()["endpoint_data"]
    for group, gdata in ed.items():
        for api, adata in gdata["apis"].items():
            for ep, val in adata["endpoints"].items():
                assert 0 <= val <= 10000, f"Unreasonable value {val} for {group}/{api}/{ep}"

def test_cache_returns_same_result():
    r1 = client.get("/api/of/ecosystem-stats")
    r2 = client.get("/api/of/ecosystem-stats")
    assert r1.json() == r2.json()
```

### 9.2 Verificações manuais pós-deploy

1. Abrir o HTML no browser → seletor mostra as 7 instituições disponíveis
2. Selecionar cada uma das 7 → todos os gráficos renderizam sem erro no console
3. Copiar URL com `?institution=NUBANK` → colar em nova aba → mesmo perfil carrega
4. URL com institution inexistente → erro amigável visível (não tela em branco)
5. Network tab: cada troca de instituição dispara exatamente 2 requests (`/receptor-profile` + `/ecosystem-stats`)
6. Segunda seleção da mesma instituição em sequência: sem nova request ao backend (cache hit)

---

## 10. Ordem de implementação recomendada

O agente deve seguir esta ordem para ter feedback rápido a cada passo:

1. **Criar `of_analytics.py`** com as funções `get_institutions`, `get_ecosystem_stats`, `get_receptor_profile`
2. **Criar `openfinance.py`** (router) com os 3 endpoints usando as funções acima
3. **Registrar o router em `main.py`**
4. **Rodar `pytest tests/test_of_endpoints.py`** — todos os testes devem passar
5. **Adaptar o frontend** (`bradesco_receptor_profile.html`):
   - Adicionar institution selector
   - Implementar `loadProfile()`
   - Conectar cada seção de renderização à resposta da API
   - Remover dados hardcoded
6. **Verificações manuais** (Seção 9.2)

---

## 11. Restrições e decisões já tomadas

| Decisão | Valor escolhido | Motivo |
|---|---|---|
| Excluir da análise | `api IN ('consents','resources')` e `status != 200` | Esses endpoints não representam consumo de dados |
| Normalização | `(req_week / consents) * (30/7)` | Converte dados semanais em métrica mensal comparável |
| Consents para PJ | coluna `cnpj` de `unique_consents` | Endpoints de pessoa jurídica devem ser normalizados por base PJ |
| Consents para PF | coluna `cpf` de `unique_consents` | Endpoints de pessoa natural devem ser normalizados por base PF |
| Consents para demais | coluna `total` de `unique_consents` | Total de consentimentos únicos |
| Detecção PJ | `"jurídica" in endpoint.lower()` | Padrão consistente nos nomes de endpoints do OFB |
| Detecção PF | `"natural" in endpoint.lower()` | Padrão consistente nos nomes de endpoints do OFB |
| Cálculo de Q3 | `median(upper_half)` onde `upper_half = sorted_vals[n - n//2:]` | Simétrico ao método de Q1; comportamento consistente com protótipo |
| Cache backend | `cachetools.TTLCache`, TTL 1h | Simples, sem dependência externa (Redis etc.) |

---

## 12. Dados do banco (referência)

| Atributo | Valor |
|---|---|
| Arquivo | `consents - Filtrado.db` |
| Tabelas | `api_requests`, `unique_consents` |
| Receptores disponíveis | BANCO DO BRASIL, BRADESCO, CAIXA ECONOMICA FEDERAL, ITAÚ UNIBANCO, MERCADO PAGO, NUBANK, SANTANDER BRASIL |
| APIs de negócio | accounts, bank-fixed-incomes, credit-cards-accounts, credit-fixed-incomes, customers, exchanges, financings, funds, invoice-financings, loans, treasure-titles, unarranged-accounts-overdraft, variable-incomes |
| Período | 2025-06-06 a 2026-03-06 (api_requests) |
| Status codes | 200 (sucesso), 500 (erro) — usar apenas status = 200 |

**Schema `api_requests`:** `date TEXT, receptor TEXT, receptor_uuid TEXT, transmitter TEXT, transmitter_uuid TEXT, api TEXT, endpoint TEXT, endpoint_id INT, status INT, total INT, fetched_at TEXT`

**Schema `unique_consents`:** `date TEXT, receptor TEXT, receptor_uuid TEXT, cpf INT, cnpj INT, total INT, fetched_at TEXT`

---

*Versão: v1.0 — Abril 2026*
