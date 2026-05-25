# Implementation Plan: Active Consents Collection

**Branch**: `001-active-consents` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-active-consents/spec.md`

---

## Summary

Extend the `data-loader` collection pipeline to capture active-consent totals per receptor × transmitter combination from `https://dashboard.openfinancebrasil.org.br/transactional-data/active-consents/receivers`. A new `active_consents` table is added to `consents.db`; collection is integrated into the existing `run_collection()` pipeline after `run_consents()` and before `run_api_requests()`. One HTTP POST call per receptor per date-range chunk returns all transmitter breakdowns — no hierarchical probe needed. Existing telemetry patterns (`fetch_attempts`, `run_summary`, `already_done()`) apply unchanged.

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Playwright (browser session + HTTP via `page.request.post()`), tenacity (retry policy), sqlite3 stdlib (DB writes)

**Storage**: SQLite — `data-loader/data/consents.db`. New table `active_consents`; two additive columns on `run_summary`.

**Testing**: pytest with real in-memory SQLite (Constitution II mandate); `httpx.AsyncClient` not required (data-loader only, no FastAPI endpoint)

**Target Platform**: Local workstation (Windows/Linux), same as current data-loader

**Project Type**: CLI data pipeline (`python main.py run`)

**Performance Goals**: ≤20% increase in total collection time vs. baseline (Spec SC-005). 1 call per receptor per week (Spec SC-003).

**Constraints**: `DEFAULT_WORKERS=4` ceiling; all SQL parameterized; no ORM; additive schema only; dashboard out-of-scope.

**Scale/Scope**: Same receptor count as existing pipeline (~20–50 receptors); one new table; two new `run_summary` columns.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- [x] **I. Code Quality**: No new abstraction without ≥3 call sites — `fetch_active_consents_for_org` mirrors `fetch_consents_for_org` exactly; no new shared abstraction introduced. `active_consents_target()` in telemetry has 1 call site (same count as `consents_target()`); it's introduced because SQL-construction correctness risk justifies even a single-site helper (constitution exemption). Type annotations required on all new public signatures.
- [x] **II. Testing**: Integration test against real in-memory SQLite for `upsert_active_consents` and the `already_done()` idempotency path. No DB mocking.
- [x] **III. UX Consistency**: No dashboard changes in this scope. N/A.
- [x] **IV. Performance**: Probe pruning N/A — active-consents endpoint returns all transmitters in a single call per receptor (SC-003). This is a consent-layer endpoint (same category as `run_consents`, not `run_api_requests`). No `fetch_api_combo()` is involved. Constitution IV probe requirement applies to api-request-style paths only.
- [x] **V. Paradigm**: data-loader only; no cross-component import; `INSERT OR REPLACE` with parameterized SQL; schema change is additive; `OPF_DB_PATH` env override chain unchanged.

**Complexity Tracking**: No violations requiring justification beyond the IV note above.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-active-consents/
├── plan.md              ← this file
├── research.md          ← Phase 0: endpoint research + design decisions
├── data-model.md        ← Phase 1: table DDL + migrations
├── quickstart.md        ← Phase 1: operator guide + acceptance checks
├── contracts/
│   └── scrapers-active-consents.md  ← Phase 1: function contracts
└── tasks.md             ← Phase 2 (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
data-loader/
├── scrapers.py          ← New: _ACTIVE_CONSENTS_PAGE_URL, _ACTIVE_CONSENTS_API_URL
│                             open_db() additions (active_consents table + index + run_summary migration)
│                             fetch_active_consents_for_org()
│                             build_active_consent_records()
│                             upsert_active_consents()
│                             _worker_run_active_consents()
│                             run_active_consents()
├── collector.py         ← Modified: run_collection() adds Phase 1b call to run_active_consents()
│                             _sync_csv() call for data/active_consents.csv
├── telemetry.py         ← New: active_consents_target() helper
│                             run_summary migration guards for two new columns
│                             finalize_run() updated to aggregate phase_active_consents_ok/failed
└── data/
    └── active_consents.csv   ← generated at runtime (not committed)

tests/                         ← integration tests (Constitution II)
├── test_active_consents_upsert.py    ← upsert + idempotency
└── test_active_consents_pipeline.py  ← end-to-end with mock HTTP responses
```

**Structure Decision**: Single-project (data-loader only). No dashboard changes. Follows the existing flat module layout — no new packages or directories in source.

---

## Phase 0 Deliverables ✅

- [x] [research.md](research.md) — endpoint hypothesis documented; runtime discovery steps defined; telemetry naming decided; worker strategy confirmed; pipeline insertion point decided

## Phase 1 Deliverables ✅

- [x] [data-model.md](data-model.md) — `active_consents` DDL + index; `run_summary` additive migration; `fetch_attempts` rows schema; entity relationships
- [x] [contracts/scrapers-active-consents.md](contracts/scrapers-active-consents.md) — contracts for `fetch_active_consents_for_org`, `upsert_active_consents`, `run_active_consents`, `open_db` additions, `telemetry.active_consents_target`
- [x] [quickstart.md](quickstart.md) — operator guide; endpoint verification steps; acceptance SQL queries; troubleshooting table

## Phase 2 (pending)

Run `/speckit-tasks` to generate the task breakdown from this plan.
