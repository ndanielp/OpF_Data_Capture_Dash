# OpF Data Capture & Dashboard

Sistema de coleta e visualização de dados do Open Finance Brasil.

## Estrutura

```
OpF_Data_Capture_Dash/
├── data-loader/    # Coleta local via Playwright + sincronização para GCS
│   └── data/consents.db   ← fonte única de dados em dev local
└── dashboard/      # Dashboard FastAPI + deploy no Google Cloud Run
```

Em dev local há uma **única cópia do SQLite** em `data-loader/data/consents.db`.
O dashboard auto-detecta esse caminho via [`dashboard/config.py`](dashboard/config.py)
(ou via env var `OPF_DB_PATH`). Em Cloud Run, o `entrypoint.sh` baixa o DB do GCS
para `/app/data/consents.db`.

## data-loader

```bash
cd data-loader
pip install -r requirements.txt
playwright install chromium

python main.py run              # coleta das últimas 4 semanas
python main.py status           # resumo dos dados locais
python main.py last-run         # último log de execução
python main.py preview consents --rows 20
```

Para agendar via Task Scheduler, use `run_job.bat`.
Ver [data-loader/README.md](data-loader/README.md) para detalhes.

## dashboard

```bash
cd dashboard

# Dev local (Python direto, lê o DB do data-loader)
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Dev local (Docker — monta ../data-loader/data como /app/data)
docker compose up

# Deploy completo no Cloud Run (sync + build + push + deploy)
.\deploy.ps1
.\deploy.ps1 -SyncOnly    # só sobe consents.db pro GCS
.\deploy.ps1 -SkipSync    # só rebuild + deploy
```

## Fluxo de dados

```
[data-loader]  coleta  →  data-loader/data/consents.db
                              │
                              ├─ dev local (auto-detect)  →  [dashboard local]
                              │
                              └─ sync_to_gcs.py  →  gs://opf-data-bucket/data/consents.db
                                                       │
                                                       └─ entrypoint.sh download
                                                              ↓
                                                    [dashboard Cloud Run]
```
