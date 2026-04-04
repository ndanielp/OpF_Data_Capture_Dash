# Open Finance Brasil — POC

Scraper + dashboard para dados públicos do portal openfinancebrasil.org.br.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Rodar

```bash
python app.py
# Abre http://localhost:5432 automaticamente
```

## Arquitetura

```
app.py              → entry-point: inicia Flask + abre browser
server.py           → backend Flask (porta 5432)
  /                 → serve gui/index.html (SPA)
  /api/stats        → totais do banco SQLite
  /api/consents     → dados de consentimentos
  /api/api-requests → dados de chamadas de API
  /api/receptors    → lista de receptores
  /api/collect/start   (POST) → inicia coleta em background
  /api/collect/stop    (POST) → para coleta
  /api/collect/stream  (GET)  → SSE: progresso em tempo real
gui/index.html      → SPA: aba Coleta + aba Dashboard (Chart.js)
build_consents_db.py    → scraper de consentimentos (Playwright)
build_api_requests_db.py → scraper de API requests (Playwright)
utils.py            → helpers: browser, retry, proxy
data/consents.db    → banco SQLite (criado automaticamente)
```

## Variáveis de ambiente opcionais

| Variável | Descrição |
|---|---|
| `CHROMIUM_BIN` | Caminho do executável Chromium (auto-detectado se omitido) |
| `HTTP_PROXY` / `HTTPS_PROXY` | Proxy para o Playwright |

## Banco de dados

O banco é criado automaticamente em `data/consents.db` na primeira coleta.
Tabelas: `consents`, `api_requests`.

## Notas

- O scraper usa Playwright headless para extrair dados do portal público
- Coleta paralelizada por workers (padrão: 3); configurável na UI
- CloudFront pode bloquear com 403 se muitos workers rodarem simultaneamente
  → reduza workers ou aguarde alguns minutos
