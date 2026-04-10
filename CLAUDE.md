# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

System for collecting and visualizing Open Finance Brasil (OpF) data. Two independent components with separate venvs:

- **`data-loader/`** — runs locally; collects data via Playwright + stores in SQLite + syncs to GCS
- **`dashboard/`** — deployed on Google Cloud Run; reads `consents.db` from GCS; serves FastAPI + Chart.js frontend

## Commands

### data-loader

```bash
cd data-loader

# Setup (first time)
pip install -r requirements.txt
playwright install chromium

# Run collection
python main.py run                          # last 4 weeks, all receptors
python main.py run -s 1w -e today -r Bradesco   # 1 week, single receptor
python main.py run -s 3m -r Itau Nubank    # 3 months, multiple receptors (substring match)
python main.py run -w 4                    # parallel workers

# Inspect
python main.py status       # CSV stats + recent runs
python main.py last-run     # tail of latest log
python main.py preview consents --rows 20

# Sync to GCS after collection
python sync_to_gcs.py
```

### dashboard

```bash
cd dashboard

# Local dev
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Docker
docker compose up

# Deploy to Cloud Run
.\deploy.ps1           # sync data + build + push + deploy
.\deploy.ps1 -SyncOnly
.\deploy.ps1 -SkipSync
```

## Architecture

### Data Flow

```
[Local] main.py run
    └─ collector.py
        ├─ Phase 1: scrapers.run_consents()
        │     OpFSession.post("/api/unique-consents") → unique_consents table
        ├─ Phase 2: _active_receptors() → filter to receptors with data
        └─ Phase 3: scrapers.run_api_requests()
              probe_receptor() → probe_transmitter() → probe_api() → fetch_api_combo()
              POST /api/api-requests → api_requests table
                                           ↓
                               data/consents.db (SQLite)
                                           ↓
                               sync_to_gcs.py → GCS bucket
                                           ↓
                               dashboard/server.py (Cloud Run)
```

### SQLite Schema (`data/consents.db`)

Four tables:
- `unique_consents` — weekly consent counts per receptor (`receptor_uuid`, `date`, `total`, `cpf`, `cnpj`)
- `api_requests` — API call metrics per receptor × transmitter × api × endpoint × status × date
- `fetch_attempts` — telemetry: 1 row per HTTP call (phase, target, status, duration_ms, records_count)
- `run_summary` — 1 row per run_id with aggregated counters (ok/failed/skipped)

### Session & HTTP

`OpFSession` (`session.py`) manages a single Playwright browser + page that navigates `dashboard.openfinancebrasil.org.br` to acquire CloudFront cookies, then makes `page.request.post()` / `page.request.get()` calls (HTTP direct, not DOM interaction). Error classification:
- `OpFTransientError` → retried via `@_RETRY_POLICY` (tenacity, 3 attempts, exponential backoff)
- `OpFFatalError` → aborts immediately

`browser.py` handles anti-detection (webdriver spoof, user-agent, proxy support via `PLAYWRIGHT_PROXY` env).

### Collection Pipeline Details

**Hierarchical probe strategy** (3-level pruning before full data fetch):
1. `probe_receptor()` — receptor-level, no transmitter/api filter
2. `probe_transmitter()` — receptor + transmitter, skip if 0 results
3. `probe_api()` — receptor + transmitter + api, skip if 0 results
4. `fetch_api_combo()` — full query with endpoint + status

Each level records a `status='skipped'` row in `fetch_attempts` when pruned. This reduces calls by ~55–70% compared to flat iteration.

**Multiprocessing**: `run_api_requests` and `run_consents` use `ProcessPoolExecutor` with workers sharing a `Manager().Queue()` for progress. Each worker owns 1 OpFSession. Workers stagger start by `_WORKER_STAGGER` seconds to avoid simultaneous bootstraps.

**Checkpoint/resumability**: `telemetry.already_done()` checks `fetch_attempts` for `status IN ('ok','empty')` before each call — allows resuming interrupted runs within the same day without re-fetching.

### Telemetry

`telemetry.py` writes to `fetch_attempts` and `run_summary`. Key query:

```sql
-- Efficiency summary for a run
SELECT phase_api_ok, phase_api_skipped, phase_api_failed, total_upserted
FROM run_summary WHERE run_id = '2026-04-09_17-42-33';

-- Skips by type
SELECT target LIKE 'probe_transmitter|%' AS is_l1,
       target LIKE 'probe_api|%' AS is_l2,
       COUNT(*)
FROM fetch_attempts WHERE run_id = ? AND status = 'skipped'
GROUP BY 1, 2;
```

### Dashboard API

`dashboard/server.py` exposes FastAPI endpoints that read SQLite directly (no ORM). Key filters accepted via query params: `start`, `end` (YYYY-MM-DD), `receptors` (comma-separated substring match). The frontend is a single HTML file at `dashboard/gui/dashboard.html` using Chart.js.

## Key Configuration

**`data-loader/config.py`**: `DB_PATH`, `LOG_DIR`, `DATA_DIR`, `META_CACHE_PATH` (API/endpoint discovery cache, 24h TTL), `DEFAULT_WORKERS=4`.

**`.env` overrides** (copy `.env.example`): `LOCAL_LOG_DIR`, `DB_PATH`, `DEFAULT_WORKERS`.

**GCS env vars** (Cloud Run): `GCS_BUCKET`, `GCS_PREFIX` (default `data/`), `GOOGLE_CLOUD_PROJECT`.

## API Payload Reference

Both collection endpoints are on `https://dashboard.openfinancebrasil.org.br`:

- `POST /api/unique-consents` — fields: `dates`, `orgs` (list of UUIDs), `role` (`"client"`)
- `POST /api/api-requests` — fields: `axis` (`"date"`), `phase` (`"transactional-data"`), `receivers`, `dates`; optional: `transmitters`, `apis`, `endpoints`, `status`

Omitting optional fields in `/api/api-requests` acts as "no filter" — used by the probe functions.
