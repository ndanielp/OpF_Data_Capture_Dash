# Contract: scrapers.py — Active Consents Functions

**Feature**: `001-active-consents`  
**Created**: 2026-05-25  
**Updated**: 2026-05-25 — endpoint confirmed via Playwright probe (R-01)  
**Component**: `data-loader/scrapers.py`

---

## `fetch_active_consents_for_org`

```python
def fetch_active_consents_for_org(
    session: OpFSession,
    receptor_uuid: str,
    transmitter_uuid: str,
    dates: list[str],
) -> list[dict]:
    ...
```

### Responsibility
POST to `POST /api/consents` for one receptor×transmitter pair, returning a list of per-date value records. Raises `OpFTransientError` or `OpFFatalError` on HTTP failure (caught by `@_RETRY_POLICY`).

### Confirmed endpoint (R-01)
- **Path**: `/api/consents` (NOT `/api/active-consents`)
- **Body**: `{"dates": [...], "clients": [receptor_uuid], "servers": [transmitter_uuid], "role": "client"}`
- **Response**: `[{"value": int, "date": "YYYY-MM-DDTHH:MM:SS.000Z"}]` — one entry per date, NO transmitter field

### Preconditions
- `session` is an authenticated `OpFSession` (browser bootstrapped, CloudFront cookies valid)
- `receptor_uuid` is a valid receptor UUID string (e.g. `"a1b2c3d4-..."`)
- `transmitter_uuid` is a valid transmitter UUID string — used as `servers` filter
- `dates` is a non-empty list of ISO-date strings (weekly grain, e.g. `["2026-04-28", "2026-05-05"]`)

### Postconditions (success)
Returns `list[dict]`, where each element has:
```python
{
    "value": int,   # total active consents for the pair on this date
    "date": str,    # ISO datetime "YYYY-MM-DDTHH:MM:SS.000Z"
}
```
Returns `[]` (empty list) when the source returns no data for this pair/date range.

### Error contract
- `OpFTransientError` — 5xx or network timeout → retried by `@_RETRY_POLICY`
- `OpFFatalError` — 4xx (auth, forbidden) → bubbles up, aborts the worker
- Any other exception → propagated as-is (not silenced)

### Side effects
None. Does not write to DB. Does not log telemetry. Callers are responsible for both.

---

## `build_active_consent_records`

```python
def build_active_consent_records(
    raw: list[dict],
    receptor_uuid: str,
    transmitter_uuid: str,
    fetched_at: str,
) -> list[dict]:
    ...
```

### Responsibility
Transform the raw API response `[{"value", "date"}]` into DB-ready records. The `transmitter_uuid` comes from the call context (it was used as the `servers` filter — the response does not include it).

### Postconditions
Returns list of dicts with keys: `receptor_uuid`, `transmitter_uuid`, `date`, `total`, `cpf` (None), `cnpj` (None), `fetched_at`.

---

## `upsert_active_consents`

```python
def upsert_active_consents(
    con: sqlite3.Connection,
    records: list[dict],
    fetched_at: str,
) -> int:
    ...
```

### Responsibility
Bulk-upsert a list of active-consent records into `active_consents` table. Returns the number of rows written.

### Preconditions
- `con` is an open, writable `sqlite3.Connection` with the `active_consents` table already created
- `records` elements have at minimum: `receptor_uuid`, `transmitter_uuid`, `date`, `total`
- `fetched_at` is an ISO datetime string (UTC)

### Postconditions
- Each record is upserted via `INSERT OR REPLACE INTO active_consents` (composite PK handles dedup)
- Returns count of rows inserted/replaced

### Error contract
- Raises `sqlite3.Error` on DB failure (caller handles)
- Does NOT commit — caller is responsible for `con.commit()`

---

## `run_active_consents`

```python
def run_active_consents(
    dates: list[str],
    db_path: str,
    workers: int,
    logger: logging.Logger,
    delay_min: float,
    delay_max: float,
    run_id: str,
    receptor_filter: list[str] | None = None,
) -> dict[str, int]:
    ...
```

### Responsibility
Orchestrate parallel collection of active consents for all receptor×transmitter pairs × date range. Returns a summary dict with `ok`, `failed`, `skipped` counts (for `run_summary` aggregation).

### Preconditions
- DB at `db_path` is initialized (tables exist)
- `dates` is a list of ISO date strings for the requested range
- `workers` ≥ 1; typically `DEFAULT_WORKERS=4`
- `receptor_filter` is `None` (all receptors) or a list of substring-match patterns

### Postconditions
- `active_consents` table populated/updated for all matching receptor × transmitter × date combinations
- `fetch_attempts` table has one row per receptor×transmitter pair per date range chunk (status = `ok`, `empty`, or `failed`)
- Returns `{"ok": N, "failed": M, "skipped": K}` where K = pairs skipped via `already_done()`

### Checkpoint behaviour
Calls `telemetry.already_done(db_path, target)` for each pair before fetching; target includes both receptor and transmitter UUIDs for per-pair granularity. Skips if already done in any prior run on the same calendar day.

### Side effects
- Writes to `active_consents` table (upsert)
- Writes to `fetch_attempts` table (one row per receptor×transmitter pair)
- Does NOT write to `run_summary` (caller `run_collection()` does that via `finalize_run()`)

---

## `open_db` additions

```sql
-- New table DDL (added to open_db())
CREATE TABLE IF NOT EXISTS active_consents (
    receptor_uuid    TEXT    NOT NULL,
    transmitter_uuid TEXT    NOT NULL,
    date             TEXT    NOT NULL,
    total            INTEGER NOT NULL,
    cpf              INTEGER,
    cnpj             INTEGER,
    fetched_at       TEXT    NOT NULL,
    PRIMARY KEY (receptor_uuid, transmitter_uuid, date)
);

CREATE INDEX IF NOT EXISTS idx_active_consents_receptor_date
    ON active_consents (receptor_uuid, date);
```

Additive only — existing tables and indexes are not modified.

---

## `telemetry.py` additions

```python
def active_consents_target(
    receptor_uuid: str, dates: list[str], transmitter_uuid: str = "",
) -> str:
    """Build the canonical target string for an active-consents fetch attempt.

    Includes transmitter_uuid for per-pair checkpoint granularity.
    Format: active_consents|||{receptor}|||{transmitter}|{date_first}_{date_last}
    """
    txm = transmitter_uuid or ""
    return f"active_consents|||{receptor_uuid}|||{txm}|{dates[0][:10]}_{dates[-1][:10]}"
```

Added alongside existing `consents_target()`.
