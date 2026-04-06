# Open Finance Data Loading & Dashboard

Coleta automatizada de dados do Open Finance Brasil com **Dashboard Analítico** publicado no Google Cloud Run.

- **Coleta (Batch)**: roda localmente com Playwright, salva em `data/consents.db`
- **Dashboard**: publicado no Google Cloud Run, lê dados do GCS

🌐 **Dashboard ao vivo:** https://opf-dashboard-904097901801.us-central1.run.app

---

## Arquitetura

```
[Local] python main.py run  →  data/consents.db
                ↓
        python sync_to_gcs.py  →  gs://opf-data-bucket/data/consents.db
                                            ↓
                                [Cloud Run: Dashboard FastAPI]
```

---

## Pré-requisitos

| Ferramenta | Para quê |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Rodar localmente ou fazer deploy |
| [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) | Deploy no Cloud Run |
| Python 3.11+ | Coleta local e sync |

---

## Coleta de Dados (Local)

### Via Python direto

```bash
# Instalar dependências
pip install -r requirements.txt
playwright install chromium

# Executar coleta (padrão: últimas 4 semanas)
python main.py run

# Outros comandos disponíveis
python main.py status          # resumo dos dados coletados
python main.py last-run        # último log de execução
python main.py preview consents --rows 20
```

### Via Docker

```bash
docker compose up batch
```

Coleta os dados e encerra automaticamente. Para customizar o período:

```yaml
# docker-compose.yml → seção batch:
command: ["python", "main.py", "run", "--start-date", "2024-01-01", "--end-date", "2024-12-31"]
```

---

## Dashboard Local

```bash
# Via Python
python main.py dashboard --port 8000

# Via Docker
docker compose up dashboard
```

Acesse: **http://localhost:8000**

---

## Publicar no Google Cloud Run

### 1. Sincronizar dados após cada coleta

```powershell
python sync_to_gcs.py
```

Sobe `data/consents.db` para `gs://opf-data-bucket/data/consents.db`.

> Requer autenticação: `gcloud auth application-default login`

### 2. Deploy após alterações de código

```powershell
# Deploy completo (sync + build + push + deploy)
.\deploy.ps1

# Só sincronizar dados (sem rebuild)
.\deploy.ps1 -SyncOnly

# Só rebuild + deploy (sem sync de dados)
.\deploy.ps1 -SkipSync
```

---

## Estrutura do Projeto

```
opf_data_loading_batch/
├── main.py               # CLI principal (run, status, dashboard, ...)
├── collector.py          # Orquestrador da coleta
├── scrapers.py           # Scrapers Playwright
├── browser.py            # Gerenciamento de browsers
├── dashboard_server.py   # Backend FastAPI do dashboard
├── config.py             # Caminhos e configurações
│
├── gcs_sync.py           # Módulo de sync bidirecional com GCS
├── sync_to_gcs.py        # Script: sobe consents.db para o GCS
├── deploy.ps1            # Script: rebuild + deploy no Cloud Run
├── entrypoint.sh         # Startup do container (baixa DB do GCS)
│
├── Dockerfile            # Imagem para o Cloud Run (dashboard only)
├── docker-compose.yml    # Uso local (dashboard + batch)
│
├── gui/                  # Frontend HTML/JS do dashboard
├── data/                 # banco SQLite (ignorado pelo git)
└── logs/                 # logs das coletas (ignorado pelo git)
```

---

## Variáveis de Ambiente (.env)

Copie `.env.example` para `.env` e ajuste:

```env
LOCAL_LOG_DIR=logs
DB_PATH=data/consents.db
DEFAULT_WORKERS=4
```

Para o Cloud Run, as variáveis `GCS_BUCKET` e `GOOGLE_CLOUD_PROJECT` são definidas automaticamente pelo `deploy.ps1`.
