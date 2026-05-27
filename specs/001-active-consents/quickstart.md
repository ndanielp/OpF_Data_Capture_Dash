# Quickstart: Active Consents Collection

**Feature**: `001-active-consents`  
**Created**: 2026-05-25

---

## Prerequisites

- `data-loader/` venv activated and Playwright Chromium installed
- `data-loader/data/consents.db` exists (run at least one standard collection first, or `python main.py run` initializes the DB)
- Active internet connection to `dashboard.openfinancebrasil.org.br`

---

## Step 0: Verify endpoint shape (one-time, before first implementation)

Before writing any code, confirm the actual API endpoint by inspecting network traffic:

1. Open Chrome and navigate to `https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers`
2. Open DevTools → Network tab → filter for `Fetch/XHR`
3. Select any receptor and a recent date range in the UI
4. Find the POST request that loads the transmitter data — capture:
   - Exact URL path (expected: `/api/active-consents`)
   - Request body JSON (expected: `{"dates": [...], "orgs": ["<uuid>"], "role": "client"}`)
   - Response body structure (verify transmitter-level breakdown exists)
5. Update `_ACTIVE_CONSENTS_API_URL` in `scrapers.py` if the path differs from the hypothesis

---

## Running active consents collection

Active consents are collected automatically as part of the standard `run` command — no separate command is needed (FR-003):

```bash
cd data-loader

# Collect last 4 weeks for all receptors (includes active_consents)
python main.py run

# Targeted collection
python main.py run -s 1w -e today
python main.py run -s 3m -r Bradesco

# With explicit workers
python main.py run -w 4
```

---

## Verifying results

```bash
# Preview table contents
python main.py preview active_consents --rows 20

# Check telemetry for the last run
python main.py status

# Direct SQL inspection
sqlite3 data/consents.db \
  "SELECT receptor_uuid, transmitter_uuid, date, total FROM active_consents LIMIT 20;"

# Row count per receptor × week
sqlite3 data/consents.db \
  "SELECT receptor_uuid, date, COUNT(*) AS transmitters, SUM(total) AS total_consents \
   FROM active_consents GROUP BY receptor_uuid, date ORDER BY date DESC LIMIT 40;"

# run_summary with active_consents counters
sqlite3 data/consents.db \
  "SELECT run_id, phase_active_consents_ok, phase_active_consents_failed \
   FROM run_summary ORDER BY run_id DESC LIMIT 5;"
```

### Expected output
After a 4-week run, `active_consents` should contain multiple rows per (receptor_uuid, date) pair — one row per active transmitter. At least one row should exist per week of the requested range for any receptor with active consents.

---

## Acceptance check (from spec SC-001 / SC-002)

```bash
# SC-001: At least one row per active receptor × transmitter combination per week
sqlite3 data/consents.db \
  "SELECT date, COUNT(DISTINCT receptor_uuid || '|' || transmitter_uuid) AS combos \
   FROM active_consents GROUP BY date ORDER BY date;"

# SC-002: Zero duplicate PKs (INSERT OR REPLACE guarantees this, but verify)
sqlite3 data/consents.db \
  "SELECT receptor_uuid, transmitter_uuid, date, COUNT(*) AS cnt \
   FROM active_consents GROUP BY receptor_uuid, transmitter_uuid, date HAVING cnt > 1;"
# Expected: 0 rows

# SC-004: All fetch_attempts for active_consents have a valid status
sqlite3 data/consents.db \
  "SELECT status, COUNT(*) FROM fetch_attempts \
   WHERE phase = 'active_consents' GROUP BY status;"
# Expected: rows with status IN ('ok', 'empty', 'failed') only
```

---

## Re-running for the same period (idempotency)

Running twice for the same date range is safe — `INSERT OR REPLACE` updates existing rows without duplicating them (FR-005). The `already_done()` checkpoint also skips receptors already collected in a prior run on the same calendar day, reducing unnecessary API calls (FR-007).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `active_consents` table empty after run | Endpoint path wrong | Re-run Step 0 to confirm path |
| `fetch_attempts.status = 'failed'` for all rows | Auth/cookie issue | Browser session expired; restart collection |
| `run_summary.phase_active_consents_ok = 0` but no errors | Receptor filter too narrow | Check `-r` filter or omit it |
| Duplicate rows in `active_consents` | `INSERT OR REPLACE` not used | Verify `upsert_active_consents()` uses correct SQL |
