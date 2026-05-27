---
description: "Task list for active consents collection feature"
---

# Tasks: Active Consents Collection

**Input**: Design documents from `/specs/001-active-consents/`

**Prerequisites**:
- [plan.md](plan.md) — technical context, project structure
- [spec.md](spec.md) — user stories US1 (P1) and US2 (P2)
- [data-model.md](data-model.md) — `active_consents` DDL, `run_summary` migration
- [contracts/scrapers-active-consents.md](contracts/scrapers-active-consents.md) — function signatures and contracts
- [research.md](research.md) — endpoint hypothesis, telemetry naming, pipeline decisions
- [quickstart.md](quickstart.md) — acceptance SQL queries, endpoint verification steps

> ✅ **Endpoint confirmed (2026-05-25)**: Verified via Playwright probe. Real endpoint is `POST /api/consents` (NOT `/api/active-consents`). Body: `{"dates", "clients", "servers", "role"}`. Response: `[{"value", "date"}]` — aggregated, no transmitter field. Per-transmitter breakdown requires 1 call per receptor×transmissor pair. Implementation updated accordingly.

**Tests**: Integration tests are **mandatory** per [Constitution II](../../.specify/memory/constitution.md) — every new DB upsert and the `already_done()` guard must have integration tests against a real in-memory SQLite instance.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files or independent logic, no unresolved deps)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Foundational — Telemetry & Schema

**Purpose**: Shared infrastructure that both user stories depend on. Must be complete before any US1 or US2 implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Add `active_consents_target(receptor_uuid, dates)` helper to `data-loader/telemetry.py` alongside `consents_target()` — returns `f"active_consents|||{receptor_uuid}|{dates[0]}_{dates[-1]}"`
- [x] T002 [P] Add `run_summary` additive-migration guards to `data-loader/telemetry.py` for columns `phase_active_consents_ok` and `phase_active_consents_failed` (follow the existing `try/except sqlite3.OperationalError: pass` pattern at lines 71–74)
- [x] T003 Update `finalize_run()` in `data-loader/telemetry.py` to aggregate `phase_active_consents_ok` and `phase_active_consents_failed` from `fetch_attempts WHERE phase = 'active_consents'` into `run_summary`
- [x] T004 [P] Add `active_consents` table DDL, `idx_active_consents_receptor_date` index, and `run_summary` migration guards to `open_db()` in `data-loader/scrapers.py` — use DDL from [data-model.md](data-model.md); additive only

**Checkpoint**: Telemetry and schema in place — user story implementation can begin.

---

## Phase 2: User Story 1 — Automatic Collection of Active Consents (Priority: P1) 🎯 MVP

**Goal**: `python main.py run` populates `active_consents` table with all receptor × transmitter combinations for the requested period.

**Independent Test**: `python main.py run -s 1w -e today`, then `python main.py preview active_consents --rows 20` shows rows with receptor_uuid, transmitter_uuid, date, total.

### Implementation for User Story 1

- [x] T005 [P] [US1] Add constants `_ACTIVE_CONSENTS_PAGE_URL` and `_ACTIVE_CONSENTS_API_URL` to `data-loader/scrapers.py` (mirror the `_CONSENTS_PAGE_URL` / `_CONSENTS_API_URL` pattern; update URL if Step 0 verification revealed a different path)
- [x] T006 [US1] Implement `fetch_active_consents_for_org(session, org_uuid, dates)` in `data-loader/scrapers.py` — POST to `_ACTIVE_CONSENTS_API_URL`, decorate with `@_RETRY_POLICY`, raise `OpFTransientError`/`OpFFatalError` per existing session error classification; return `list[dict]` per contract in [contracts/scrapers-active-consents.md](contracts/scrapers-active-consents.md)
- [x] T007 [P] [US1] Implement `build_active_consent_records(raw, receptor_uuid, fetched_at)` in `data-loader/scrapers.py` — maps raw API response list to dicts with keys `receptor_uuid`, `transmitter_uuid`, `date`, `total`, `cpf` (nullable), `cnpj` (nullable), `fetched_at`; adjust field names to match actual response from Step 0
- [x] T008 [P] [US1] Implement `upsert_active_consents(con, records, fetched_at)` in `data-loader/scrapers.py` — `INSERT OR REPLACE INTO active_consents` with parameterized SQL (no f-string interpolation); returns row count; does NOT commit
- [x] T009 [US1] Implement `_worker_run_active_consents(worker_id, chunk, dates, fetched_at, queue, delay_min, delay_max, db_path, run_id)` in `data-loader/scrapers.py` — calls `telemetry.already_done()` guard (skip if already done), calls `fetch_active_consents_for_org()`, calls `upsert_active_consents()`, calls `telemetry.log_attempt()` with phase `"active_consents"` and target from `active_consents_target()`; mirrors `_worker_run_consents()` structure exactly
- [x] T010 [US1] Implement `run_active_consents(dates, db_path, workers, logger, delay_min, delay_max, run_id, receptor_filter)` in `data-loader/scrapers.py` — fetches org list via `fetch_orgs()`, applies `receptor_filter`, dispatches workers via `ProcessPoolExecutor` + `Manager().Queue()`; returns `{"ok": N, "failed": M, "skipped": K}`; mirrors `run_consents()` orchestration pattern
- [x] T011 [US1] Add Phase 1b call to `run_active_consents()` in `data-loader/collector.py` — insert between `run_consents()` (Phase 1a) and `run_api_requests()` (Phase 2); add `_sync_csv()` call for `data/active_consents.csv` with PK columns `["receptor_uuid", "transmitter_uuid", "date"]`

### Integration Tests for User Story 1 (Constitution II — mandatory)

- [x] T012 [P] [US1] Write integration test in `data-loader/tests/test_active_consents_upsert.py` — creates real in-memory SQLite, calls `open_db()`, calls `upsert_active_consents()` with 3 sample records, asserts row count and field values; calls `upsert_active_consents()` again with same records (updated totals), asserts zero duplicate PKs and updated values

**Checkpoint**: `python main.py run -s 1w -e today` → `active_consents` table contains rows; `python main.py preview active_consents` shows data. Run `pytest data-loader/tests/test_active_consents_upsert.py` → all tests pass.

---

## Phase 3: User Story 2 — Resilience & Observability (Priority: P2)

**Goal**: Active consent collection metrics appear in `python main.py status`; failures do not interrupt other collection phases; interrupted runs resume from checkpoint.

**Independent Test**: After a collection run, `python main.py status` shows `phase_active_consents_ok`/`failed` counts in `run_summary`; re-running for the same day skips already-collected receptors.

### Implementation for User Story 2

- [x] T013 [US2] Verify error isolation in `_worker_run_active_consents()` in `data-loader/scrapers.py` — confirm `OpFFatalError` is caught at the worker level and recorded as `status='failed'` in `fetch_attempts` without raising to the `ProcessPoolExecutor`; confirm the overall `run_collection()` continues to Phase 2 (`run_api_requests`) even if Phase 1b fails for some receptors

### Integration Tests for User Story 2 (Constitution II — mandatory)

- [x] T014 [P] [US2] Write integration test in `data-loader/tests/test_active_consents_idempotency.py` — creates real in-memory SQLite with `open_db()`; calls `_worker_run_active_consents()` for receptor A with mock HTTP response; calls it again for the same receptor + date range; asserts `already_done()` returns True on second call; asserts `fetch_attempts` contains exactly 1 row with `status='ok'` for that target (no duplicate attempt logged); asserts `active_consents` has no duplicate rows

**Checkpoint**: `python main.py status` after a run shows active_consents counters. `pytest data-loader/tests/test_active_consents_idempotency.py` passes.

---

## Phase 4: Polish & Acceptance Validation

**Purpose**: Confirm all success criteria from spec.md are met; clean up any loose ends.

- [ ] T015 [P] Run full acceptance SQL queries from [quickstart.md](quickstart.md) against a real 4-week collection: SC-001 (≥1 row per combo per week), SC-002 (0 duplicate PKs), SC-003 (fetch_attempts count ≤ receptors × weeks), SC-004 (all fetch_attempts have valid status)
- [x] T016 [P] Verify `python main.py preview active_consents` command works (no KeyError or schema mismatch in `main.py`'s `preview` dispatch table) — add `active_consents` to preview dispatch if missing
- [x] T017 Update docstrings/comments on new public functions in `data-loader/scrapers.py` and `data-loader/telemetry.py` — WHY-focused only per Constitution I (no restatements of what the code does)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No blocking dependencies — start immediately
- **Phase 2 (US1)**: Requires Phase 1 complete (`active_consents` table + telemetry helpers must exist)
- **Phase 3 (US2)**: Requires Phase 2 complete (worker and fetch functions built by US1)
- **Phase 4 (Polish)**: Requires Phase 2 + Phase 3 complete

### User Story Dependencies

- **US1**: Depends on Phase 1 only
- **US2**: Depends on US1 (T013, T014 verify behaviour of T009; T013 adds error-handling verification to existing worker)

### Within Phase 2

- T005 (constants) → T006 (uses URL constant) → T009 (uses fetch fn) → T010 (calls worker) → T011 (calls run_active_consents)
- T007 (build_records) [P] alongside T006 — pure function, no deps
- T008 (upsert) [P] alongside T006, T007 — only needs table from Phase 1
- T012 (integration test) [P] alongside T011 — different file

### Parallel Opportunities

- T001 + T004 can run in parallel (both Phase 1; T001 = telemetry.py, T004 = scrapers.py)
- T002 + T004 can run in parallel (T002 = telemetry migration, T004 = scrapers migration)
- T005 + T007 + T008 can start in parallel once Phase 1 is done
- T012 + T011 can run in parallel (different files)
- T014 + T013 can run in parallel (different files + different focus)
- T015 + T016 + T017 can all run in parallel

---

## Parallel Example: Phase 2 (User Story 1)

```bash
# Step 1: Start in parallel (once Phase 1 is done)
Task T005: Add URL constants to scrapers.py
Task T007: Implement build_active_consent_records() in scrapers.py
Task T008: Implement upsert_active_consents() in scrapers.py

# Step 2: After T005 completes
Task T006: Implement fetch_active_consents_for_org() in scrapers.py

# Step 3: After T006, T007, T008 complete
Task T009: Implement _worker_run_active_consents() in scrapers.py

# Step 4: After T009 completes
Task T010: Implement run_active_consents() in scrapers.py

# Step 5: After T010 completes (in parallel)
Task T011: Integrate into collector.py
Task T012: Write integration tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (T001–T004)
2. Complete Phase 2: User Story 1 (T005–T012)
3. **STOP and VALIDATE**: `python main.py run -s 1w -e today`, then run quickstart acceptance queries
4. Run `pytest data-loader/tests/test_active_consents_upsert.py`
5. If green: proceed to Phase 3

### Incremental Delivery

1. Phase 1 → schema and telemetry ready
2. Phase 2 → `active_consents` table populated on every run (MVP)
3. Phase 3 → resilience guarantees + idempotency verified (production-safe)
4. Phase 4 → acceptance validation complete, ready for PR

---

## Notes

- `[P]` tasks = different files or logically independent; no shared mutable state conflict
- `[Story]` label maps each task to a user story for traceability
- Tests marked `[P]` in their story's phase can be written before OR after implementation (TDD or verify-after); either is valid per Constitution II — what matters is they use real SQLite, not mocks
- If Step 0 (endpoint shape verification) reveals a response structure different from the hypothesis in [research.md](research.md), update T007 (`build_active_consent_records`) accordingly before implementing T009
- Commit after each completed phase checkpoint (not after each individual task)
