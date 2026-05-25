# Contract: scrapers.py — Active Consents Functions

**Feature**: `001-active-consents`  
**Created**: 2026-05-25  
**Component**: `data-loader/scrapers.py`

---

## `fetch_active_consents_for_org`

```python
def fetch_active_consents_for_org(
    session: OpFSession,
    org_uuid: str,
    dates: list[str],
) -> list[dict]:
    ...
```

### Responsibility
Post a single HTTP request to the active-consents endpoint for one receptor UUID, returning a list of per-transmitter-per-date records. Raises `OpFTransientError` or `OpFFatalError` on HTTP failure (caught by `@_RETRY_POLICY`).

### Preconditions
- `session` is an authenticated `OpFSession` (browser bootstrapped, CloudFront cookies valid)
- `org_uuid` is a valid receptor UUID string (e.g. `"a1b2c3d4-..."`)
- `dates` is a non-empty list of ISO-date strings (weekly grain, e.g. `["2026-04-28", "2026-05-05"]`)

### Postconditions (success)
Returns `list[dict]`, where each element has at minimum:
```python
{
    "transmitter_uuid": str,   # ⚠️ field name subject to R-01 confirmation
    "date": str,               # ISO date
    "total": int,
    # "cpf": int | None,       # optional — present only if source provides
    # "cnpj": int | None,      # optional — present only if source provides
}
```
Returns `[]` (empty list) when the source returns no data for this receptor/date range.

### Error contract
- `OpFTransientError` — 5xx or network timeout → retried by `@_RETRY_POLICY`
- `OpFFatalError` — 4xx (auth, forbidden) → bubbles up, aborts the worker
- Any other exception → propagated as-is (not silenced)

### Side effects
None. Does not write to DB. Does not log telemetry. Callers are responsible for both.

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
Orchestrate parallel collection of active consents for all receptors × date range. Returns a summary dict with `ok`, `failed`, `skipped` counts (for `run_summary` aggregation).

### Preconditions
- DB at `db_path` is initialized (tables exist)
- `dates` is a list of ISO date strings for the requested range
- `workers` ≥ 1; typically `DEFAULT_WORKERS=4`
- `receptor_filter` is `None` (all receptors) or a list of substring-match patterns

### Postconditions
- `active_consents` table populated/updated for all matching receptor × transmitter × date combinations
- `fetch_attempts` table has one row per receptor per date range chunk (status = `ok`, `empty`, or `failed`)
- Returns `{"ok": N, "failed": M, "skipped": 0}` — no skipped rows (no probe pruning for this endpoint)

### Checkpoint behaviour
Calls `telemetry.already_done(db_path, target, run_id=None)` for each receptor before fetching; skips and counts as skipped if already done in any prior run on the same calendar day.

### Side effects
- Writes to `active_consents` table (upsert)
- Writes to `fetch_attempts` table (one row per receptor)
- Does NOT write to `run_summary` (caller `run_collection()` does that via `finalize_run()`)

---

## `open_db` additions

```python
# New table DDL (added to open_db())
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
def active_consents_target(receptor_uuid: str, dates: list[str]) -> str:
    """Build the canonical target string for an active-consents fetch attempt."""
    return f"active_consents|||{receptor_uuid}|{dates[0]}_{dates[-1]}"
```

Added alongside existing `consents_target()`.
