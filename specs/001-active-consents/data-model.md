# Data Model: Active Consents Collection

**Feature**: `001-active-consents`  
**Created**: 2026-05-25  
**Phase**: 1 — Design  
**Note**: Column types marked ⚠️ are subject to confirmation of the endpoint response shape (see [research.md R-01](../research.md)).

---

## New Table: `active_consents`

```sql
CREATE TABLE IF NOT EXISTS active_consents (
    receptor_uuid  TEXT    NOT NULL,
    transmitter_uuid TEXT  NOT NULL,
    date           TEXT    NOT NULL,   -- ISO date, e.g. "2026-05-01"
    total          INTEGER NOT NULL,
    cpf            INTEGER,            -- ⚠️ NULL if source doesn't provide CPF breakdown
    cnpj           INTEGER,            -- ⚠️ NULL if source doesn't provide CNPJ breakdown
    fetched_at     TEXT    NOT NULL,   -- ISO datetime of collection
    PRIMARY KEY (receptor_uuid, transmitter_uuid, date)
);
```

### Design notes

- **Composite PK** `(receptor_uuid, transmitter_uuid, date)` makes `INSERT OR REPLACE` safe for upsert (FR-005)
- `cpf` and `cnpj` are nullable so they can be added to the DDL now and populated only when the source provides them — avoids a future schema migration
- `fetched_at` follows the same pattern as `unique_consents` (records when the row was written, not what date the data refers to)
- `date` is weekly-grain, aligned with `unique_consents.date` (Spec Assumption)
- No `receptor_name` or `transmitter_name` columns — names are derivable by joining against the org list; storing them would create update anomalies

### Index

```sql
CREATE INDEX IF NOT EXISTS idx_active_consents_receptor_date
    ON active_consents (receptor_uuid, date);
```

Supports the typical dashboard query pattern: filter by receptor + date range.

---

## Schema Migration: `run_summary`

Two new columns, added with the existing additive-migration pattern (no destructive changes):

```sql
ALTER TABLE run_summary ADD COLUMN phase_active_consents_ok     INTEGER NOT NULL DEFAULT 0;
ALTER TABLE run_summary ADD COLUMN phase_active_consents_failed INTEGER NOT NULL DEFAULT 0;
```

**Migration guard** (in `open_db()` or `telemetry.py`, following lines 71–74 pattern):

```python
for col in [
    "ALTER TABLE run_summary ADD COLUMN phase_active_consents_ok INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE run_summary ADD COLUMN phase_active_consents_failed INTEGER NOT NULL DEFAULT 0",
]:
    try:
        con.execute(col)
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
```

---

## Telemetry: `fetch_attempts` (no schema change)

No DDL change required. New rows will use:

| Column | Value pattern |
|--------|--------------|
| `phase` | `"active_consents"` |
| `target` | `f"active_consents\|\|\|{receptor_uuid}\|{date_first}_{date_last}"` |
| `status` | `"ok"` / `"empty"` / `"failed"` |
| `duration_ms` | milliseconds for the single POST call |
| `records_count` | number of transmitter rows returned (0 when `status="empty"`) |

---

## Entity Relationships

```
fetch_attempts
    phase = "active_consents"
    target = "active_consents|||{receptor_uuid}|..."
        └─ many-to-one → active_consents (receptor_uuid, date)

active_consents
    receptor_uuid  ─── [no FK; same UUID namespace as unique_consents.receptor_uuid]
    transmitter_uuid ─ [no FK; same UUID namespace as api_requests.transmitter_uuid]
    date           ─── weekly grain, same calendar as unique_consents.date

run_summary
    phase_active_consents_ok / phase_active_consents_failed
        └─ aggregated from fetch_attempts WHERE phase = "active_consents"
```

No foreign-key constraints are added (SQLite FK enforcement is off by default in this project; existing tables follow the same convention).

---

## Unchanged Tables

| Table | Change |
|-------|--------|
| `unique_consents` | None |
| `api_requests` | None |
| `fetch_attempts` | None (new rows added with new phase) |
| `run_summary` | Two columns added (additive migration) |
| `api_group_weekly` | None — active_consents is not an input to the pre-aggregation |
| `payment_api_requests` | None |
