# OpF Data Capture & Dashboard

Sistema de coleta e visualização de dados do Open Finance Brasil.

## Estrutura

```
OpF_Data_Capture_Dash/
├── data-loader/    # Coleta local via Playwright + sincronização para GCS
└── dashboard/      # Dashboard FastAPI + deploy no Google Cloud Run
```

## data-loader

Roda localmente. Coleta dados via Playwright e salva em SQLite, depois sincroniza para o GCS.

```bash
cd data-loader
pip install -r requirements.txt
playwright install chromium

python main.py run              # coleta das últimas 4 semanas
python main.py status          # resumo dos dados locais
python main.py last-run        # último log de execução
python main.py preview consents  # preview do CSV
```

Para agendar via Task Scheduler, use `run_job.bat`.

Ver [data-loader/README.md](data-loader/README.md) para detalhes.

## dashboard

Deploy no Google Cloud Run. Lê `consents.db` do GCS e serve o dashboard via FastAPI.

```bash
cd dashboard

# Testar localmente
docker compose up

# Deploy completo (sync + build + push + deploy)
.\deploy.ps1

# Só sincronizar dados
.\deploy.ps1 -SyncOnly

# Só rebuild + deploy (sem sync)
.\deploy.ps1 -SkipSync
```

## Fluxo de dados

```
[data-loader] coleta → consents.db → GCS
                                       ↓
                              [dashboard] download → FastAPI → Chart.js
```
