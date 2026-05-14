# OpF Data Loader

Coleta automatizada de dados do Open Finance Brasil via Playwright. Escreve em
`data/consents.db` (SQLite) e sincroniza para o Google Cloud Storage, de onde o
[dashboard](../dashboard/) lê em produção.

> **Onde fica o DB**: o arquivo `data/consents.db` deste diretório é a **fonte
> única** em dev local. O dashboard auto-detecta esse caminho via
> [`dashboard/config.py`](../dashboard/config.py) — não há cópia separada.

---

## Pré-requisitos

| Ferramenta | Para quê |
|---|---|
| Python 3.11+ | Executar a coleta |
| [Playwright](https://playwright.dev/python/) Chromium | Browser headless |
| [gcloud CLI](https://cloud.google.com/sdk/docs/install) | `sync_to_gcs.py` (opcional) |

---

## Setup

```bash
cd data-loader
pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # ajuste se quiser (LOCAL_LOG_DIR, DB_PATH, DEFAULT_WORKERS)
```

---

## Comandos (CLI)

```bash
# Coleta padrão: últimas 4 semanas, todos os receptores
python main.py run

# Recortes
python main.py run -s 1w -e today -r Bradesco        # 1 semana, 1 receptor
python main.py run -s 3m -r Itau Nubank              # 3 meses, vários (substring match)
python main.py run --start-date 2025-06-01           # data absoluta
python main.py run -w 4                              # workers paralelos

# Inspeção
python main.py status                # CSV stats + recent runs
python main.py last-run              # tail do log mais recente
python main.py preview consents --rows 20
python main.py preview api_requests
```

Cada run gera `logs/_global/<run_id>.log` + um log por receptor em
`logs/<receptor>/<run_id>.log`.

---

## Agendamento

`run_job.bat` é o entry point para o **Task Scheduler** do Windows:

```bat
call .venv\Scripts\python.exe main.py run --start-date "2025-06-01" --workers 1
```

Ajuste parâmetros conforme a frequência desejada. O collector é **resumível**:
chamadas já feitas com `status='ok'` ou `'empty'` em `fetch_attempts` são puladas
no próximo run do mesmo dia.

---

## Sincronizar para o GCS

Após cada coleta, suba o DB para o bucket de onde o Cloud Run lê:

```bash
python sync_to_gcs.py
```

Requer:

- Autenticação: `gcloud auth application-default login`
- Variáveis de ambiente (ou edite os defaults em `sync_to_gcs.py`):
  - `GCS_BUCKET=opf-data-bucket`
  - `GOOGLE_CLOUD_PROJECT=opf-dash`

Só o(s) `.db` é(são) sincronizado(s); CSVs ficam apenas locais.

---

## Estrutura

```
data-loader/
├── main.py             # CLI (run, status, last-run, preview)
├── collector.py        # Orquestrador: consents → probes → api_requests + telemetria
├── scrapers.py         # POST /api/unique-consents, /api/api-requests + api_group_weekly
├── session.py          # OpFSession (Playwright + CloudFront cookies + retry)
├── browser.py          # Anti-detection, proxy, parse de datas
├── telemetry.py        # fetch_attempts + run_summary
├── config.py           # Caminhos (DB_PATH, LOG_DIR, DATA_DIR, META_CACHE_PATH)
├── gcs_sync.py         # Módulo compartilhado upload/download GCS
├── sync_to_gcs.py      # Script CLI para subir o DB ao bucket
├── run_job.bat         # Entry point para Task Scheduler
├── requirements.txt
├── .env.example
├── data/               # consents.db (SQLite, ignorado pelo git)
└── logs/               # logs por run (ignorado pelo git)
```

---

## Schema SQLite

Cinco tabelas em `data/consents.db`:

| Tabela | Conteúdo |
|---|---|
| `unique_consents`  | Contagens semanais de consentimentos por receptor (total, cpf, cnpj). |
| `api_requests`     | Métricas de chamadas API por receptor × transmissor × api × endpoint × status × data. |
| `fetch_attempts`   | Telemetria: 1 linha por chamada HTTP (phase, target, status, duration_ms). |
| `run_summary`      | 1 linha por `run_id` com contadores agregados. |
| `api_group_weekly` | Pré-agregação por grupo (Conta, Cartao, Credito, Investimento, Cambio, Identidade, Resource) — populada por `scrapers.refresh_api_group_weekly`. Consumida pelo dashboard. |

---

## Variáveis de ambiente

Override via `.env`:

```env
LOCAL_LOG_DIR=logs
DB_PATH=data/consents.db
DEFAULT_WORKERS=4

# Opcionais
# CHROMIUM_BIN=/usr/bin/chromium
# HTTPS_PROXY=http://user:pass@host:port
```
