# Research: Active Consents Collection

**Feature**: `001-active-consents`  
**Created**: 2026-05-25  
**Phase**: 0 — Pre-design research

---

## R-01: Endpoint Shape (⚠️ RUNTIME DISCOVERY REQUIRED)

### Status
**Partially confirmed via spec assumptions; final payload/response shape must be verified at runtime.**

### What is known
- Source URL: `https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers`
- Spec SC-003 commits to: ≤ 1 call per receptor per week; that single call returns ALL transmitters for the receptor
- Spec Assumption: the endpoint behaves like `unique-consents` — POST with receptor UUID, returns multi-transmitter breakdown

### Likely hypothesis (must confirm)

| Attribute | Hypothesis | Basis |
|-----------|-----------|-------|
| Method | `POST` | All other collection endpoints use POST |
| Path | `/api/active-consents` | Mirrors `unique-consents` → `/api/unique-consents` naming |
| Request body | `{"dates": [...], "orgs": [receiver_uuid], "role": "client"}` | Same shape as unique-consents payload |
| Response structure | Array of objects with at least `transmitter_uuid` and `total` per date | Required by FR-001 and SC-003 |
| CPF/CNPJ breakdown | May or may not be present | Spec says "if available, may be stored" |

### Runtime verification steps (operator task)
1. Navigate to `https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers` in Chrome DevTools (Network tab)
2. Select any receptor and a date range
3. Identify the XHR/Fetch call triggered — capture: URL, method, request body, response body
4. Confirm or update:
   - Actual API path
   - Actual request fields
   - Response structure (does transmitter breakdown exist at all? is it `transmitter_uuid` or `transmitter_id`?)
   - Whether CPF/CNPJ breakdown is present

### Impact on implementation
- If path ≠ `/api/active-consents`: update `_ACTIVE_CONSENTS_API_URL` constant in `scrapers.py`
- If request body differs: update `fetch_active_consents_for_org()`
- If response does NOT have per-transmitter breakdown: the feature cannot fulfil FR-001; escalate to spec owner before implementing
- If response DOES include CPF/CNPJ: add `cpf`/`cnpj` columns to `active_consents` table (additive, safe)

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
- **Target string** (used in `fetch_attempts.target` and `already_done()` lookup): `f"active_consents|||{receptor_uuid}|{date_first}_{date_last}"`

### Rationale
- Existing patterns: `"consents"` for unique_consents, `"api_requests"` for api_requests, `"payment_initiation"` for payment
- The double-pipe separator `|||` matches the existing `consents_target()` helper format
- Using receptor_uuid + date range as the key enables `already_done()` to skip per-receptor per-date on resume (checkpoint at the right granularity — SC-003 confirms 1 call per receptor per week, so this is the natural checkpoint unit)
- A helper `active_consents_target(receptor_uuid, dates)` should be added to `telemetry.py` alongside `consents_target()`

---

## R-04: run_summary Column Additions

### Decision
Add two new columns to `run_summary` using the established additive-migration pattern:
- `phase_active_consents_ok INTEGER NOT NULL DEFAULT 0`
- `phase_active_consents_failed INTEGER NOT NULL DEFAULT 0`

No `_skipped` column needed: active-consents has no probe hierarchy — the single per-receptor call either succeeds, returns empty, or fails.

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

### Probe pruning (Constitution IV)
- **Pruning N/A for this collection path**: SC-003 explicitly states 1 call per receptor returns all transmitters — there is no per-transmitter or per-api iteration
- Constitution IV says "any new collection path MUST implement the same three-level pruning _before_ the full `fetch_api_combo()` call" — this applies to api_requests-style endpoints; active_consents is a consent-level endpoint (same category as `run_consents`, not `run_api_requests`)
- No `fetch_api_combo()` call is made; the equivalent is `fetch_active_consents_for_org()`
- **Constitution Check**: Mark IV as N/A with justification (consent endpoint, not API-request endpoint)

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
