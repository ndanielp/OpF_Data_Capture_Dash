# Research: Active Consents Collection

**Feature**: `001-active-consents`  
**Created**: 2026-05-25  
**Phase**: 0 — Pre-design research

---

## R-01: Endpoint Shape (✅ CONFIRMED via Playwright Probe — 2026-05-25)

### Status
**Confirmed.** Endpoint discovered by intercepting webpack chunks and validated with real HTTP calls.

### Confirmed findings

| Attribute | Confirmed value | Note |
|-----------|----------------|-------|
| Method | `POST` | ✅ |
| Path | `/api/consents` | ✅ — NOT `/api/active-consents` as hypothesised |
| Request body | `{"dates": [...], "clients": [receptor_uuid], "servers": [transmitter_uuid], "role": "client"}` | Field is `clients` (not `orgs`); `servers` filters to one transmitter |
| Response structure | `[{"value": int, "date": "YYYY-MM-DDTHH:MM:SS.000Z"}]` | One entry per date — aggregated total, NO transmitter_uuid field |
| CPF/CNPJ breakdown | Not present | API returns only `value` + `date` |

### Key implication: per-transmitter breakdown requires one call per receptor×transmitter pair
Without the `servers` filter, the API returns the aggregate total across all transmitters for the receptor.
To obtain per-transmitter data, the caller must issue one call per pair with `servers=[transmitter_uuid]`.
This was validated by comparing:
- `clients=[Bradesco]`, no `servers` → `value=8,587,003`
- `clients=[Bradesco]`, `servers=[99PAY]` → `value=23,792`

The hypothesis in the original spec (SC-003: "1 call per receptor returns all transmitters") was **incorrect**.
Revised approach: 1 call per receptor×transmitter pair; `transmitter_uuid` stored from call context.

---

## R-02: Receptor List Source

### Decision
**Reuse `fetch_orgs()` — the same function used by `run_consents()`.**

### Rationale
- Spec Assumption: "Os receptores de consentimentos ativos são os mesmos já presentes no sistema (mesmos UUIDs)"
- `fetch_orgs()` navigates `_CONSENTS_PAGE_URL` and intercepts `/api/organisations` — it returns all known receptor UUIDs and names
- No separate discovery step for active-consents receptors is needed
- The `receptor_filter` applied in `run_consents()` must be applied identically here (FR-004)

### Alternatives considered
- **Query `unique_consents` for known receptors** (used by `_active_receptors()`): rejected — would skip receptors with no unique-consent data yet, potentially missing active-consent data
- **Separate page navigation for active-consents/receivers**: rejected — adds a redundant browser session; same org list is served

---

## R-03: Phase Name and Telemetry Target Format

### Decision
- **Phase string** (used in `fetch_attempts.phase` and `run_summary` aggregation): `"active_consents"`
- **Target string**: `f"active_consents|||{receptor_uuid}|||{transmitter_uuid}|{date_first}_{date_last}"`

### Rationale
- Existing patterns: `"consents"` for unique_consents, `"api_requests"` for api_requests, `"payment_initiation"` for payment
- With the per-pair iteration approach (see R-01), the checkpoint key must include both receptor and transmitter — otherwise the second pair for the same receptor would be incorrectly skipped by `already_done()`
- `active_consents_target(receptor_uuid, dates, transmitter_uuid="")` helper added to `telemetry.py`; `transmitter_uuid` defaults to `""` to allow future aggregate-only collection without a transmitter filter

---

## R-04: run_summary Column Additions

### Decision
Add two new columns to `run_summary` using the established additive-migration pattern:
- `phase_active_consents_ok INTEGER NOT NULL DEFAULT 0`
- `phase_active_consents_failed INTEGER NOT NULL DEFAULT 0`

No `_skipped` column needed for the active-consents probe hierarchy; `empty` status is counted as `ok` in run_summary (data absent is a valid final state for a pair).

### Migration pattern (existing, from `telemetry.py:71-74`)
```python
try:
    con.execute("ALTER TABLE run_summary ADD COLUMN phase_active_consents_ok INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass

try:
    con.execute("ALTER TABLE run_summary ADD COLUMN phase_active_consents_failed INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass
```

---

## R-05: Worker and Parallelism Strategy

### Decision
**Reuse the existing `ProcessPoolExecutor` + `Manager().Queue()` pattern**, matching `_worker_run_consents()` structure exactly.

### Rationale
- `run_active_consents()` iterates over the same receptor list as `run_consents()` — same shape of work
- `DEFAULT_WORKERS=4` applies (configurable via `.env`); no new config needed
- Worker stagger `_WORKER_STAGGER` avoids simultaneous browser bootstraps (same as current)
- Each worker owns its own `OpFSession` (required by Playwright thread-safety model)

### Scale consideration (confirmed 2026-05-25)
The per-pair approach produces N_receptors × N_transmitters pairs. With ~50 receptors × ~100 transmitters = ~5,000 pairs per run. Workers process pairs in parallel; `already_done()` checkpoint avoids re-collecting pairs already fetched on the same day.

### Probe pruning (Constitution IV)
- **Pruning N/A for this collection path**: active_consents is a consent-level endpoint (same category as `run_consents`, not `run_api_requests`)
- Constitution IV applies to api_requests-style hierarchical probing; no `fetch_api_combo()` is called here
- **Constitution Check**: IV marked N/A with justification (consent endpoint)

---

## R-06: Insertion into `collector.py` Pipeline

### Decision
Insert `run_active_consents()` as **Phase 1b** in `run_collection()`, immediately after `run_consents()` (Phase 1a) and before `run_api_requests()` (Phase 2).

### Rationale
- Active consents are semantically a consent-layer metric, not an API-request metric
- The receptor list for Phase 2 (`_active_receptors()`) is still derived from `unique_consents` — no change needed
- Running active_consents before api_requests means a failed active_consents phase doesn't prevent API data from being collected (isolation of failures per constitution)
- `refresh_api_group_weekly()` is called at end of `run_collection()` — no change needed (active_consents is not an input to the aggregation table)

---

## R-07: CSV Export

### Decision
Add `data/active_consents.csv` export to `run_collection()` using the existing `_sync_csv()` pattern.

### Rationale
- All other tables with `date` columns have a corresponding CSV export (`data/consents.csv`, `data/api_requests.csv`)
- Consistency (Constitution I)
- PK columns for dedup: `["receptor_uuid", "transmitter_uuid", "date"]`

---

## Open Questions (deferred to implementation)

| # | Question | When to resolve |
|---|---------|----------------|
| Q1 | Exact response JSON structure (transmitter field name, CPF/CNPJ presence) | Before writing `scrapers.py` — verify via browser DevTools |
| Q2 | Whether `fetch_orgs()` already navigates to `active-consents/receivers` or only `unique-consents/receivers` | Code review during implementation — may need separate navigation |
| Q3 | Whether `already_done()` should also check cross-run (no `run_id`) for active_consents | Implementation decision — follow same pattern as `run_consents` (cross-run check with `run_id=None`) |
