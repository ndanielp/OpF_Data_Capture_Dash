<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 (template placeholder) → 1.0.0
Bump type: MINOR — first full ratification of a previously empty template.

Modified principles:
  All principles are NEW (template had only bracketed placeholders).

Added sections:
  - Core Principles (I–V)
  - Stack Constraints
  - Development Workflow
  - Governance

Removed sections:
  - None (template placeholders replaced)

Templates reviewed:
  ✅ .specify/templates/plan-template.md — Constitution Check gates now map to
     Principles I–V; no structural change needed to the template itself.
  ✅ .specify/templates/spec-template.md — User stories and acceptance scenarios
     align with Principle III (UX consistency) and Principle II (testing).
  ✅ .specify/templates/tasks-template.md — Phase structure and [P] parallel
     markers align with Principle V (implementation paradigm).

Follow-up TODOs:
  - None. All fields fully resolved.
-->

# OpF Data Capture & Dashboard Constitution

## Core Principles

### I. Code Quality & Simplicity

Every change MUST leave the codebase simpler or equally simple — never more
complex — than it found it. Concretely:

- New abstractions MUST be justified by three or more real call sites in the
  current codebase. Hypothetical future reuse is not justification.
- Helper functions MUST be introduced only when the duplicated logic creates a
  correctness risk (e.g., SQL construction, date formatting) or exceeds 10
  lines repeated verbatim.
- Comments MUST explain WHY (hidden constraint, surprising invariant, specific
  workaround). Comments that restate what the code does MUST be removed.
- Type annotations MUST be present on all public function signatures in both
  `data-loader/` and `dashboard/`.
- Dead code (unreferenced functions, unused imports, commented-out blocks) MUST
  be deleted immediately rather than preserved "for reference."

**Rationale**: The two-component architecture (data-loader + dashboard) is
maintained by a small team. Accumulated abstraction debt compounds fast and
slows feature work disproportionately.

### II. Testing Standards

Testing MUST be proportional to the risk and reversibility of the component:

- **Data pipeline** (`data-loader/`): Every new scraper path or DB upsert
  MUST have at least one integration test that writes to a real in-memory
  SQLite instance and asserts the resulting rows. Mocking the DB layer is
  PROHIBITED because the 2025 incident showed mock/prod divergence masks
  schema bugs silently.
- **Dashboard API** (`dashboard/`): Each new FastAPI endpoint MUST have at
  least one HTTP-level test (using `httpx.AsyncClient` against the real app)
  that covers the happy path and one error case.
- **Frontend** (`dashboard/gui/`): Manual browser validation against the local
  dev server (port 8000) MUST be performed before declaring any UI change done.
  Chart.js rendering, filter behavior, and page load MUST be checked.
- **Collection pipeline checkpoints**: The `telemetry.already_done()` guard
  MUST be covered by a test that verifies idempotency — running the same date
  range twice MUST NOT insert duplicate rows.
- Unit tests are OPTIONAL and only added when explicitly requested.

**Rationale**: The primary correctness risk in this system is data integrity
(wrong aggregates reach the dashboard) and UI regressions (charts break silently
when API shape changes). Tests MUST guard these boundaries, not internal
implementation details.

### III. User Experience Consistency

All dashboard views MUST share a single visual and behavioral contract:

- **Color palette**: All chart colors MUST be sourced from
  `dashboard/services/constants.py::API_GROUPS`. Hardcoded hex values in HTML
  or JavaScript are PROHIBITED.
- **Filter behavior**: Date range (`start`/`end`) and receptor filter
  (`receptors`) MUST behave identically across `dashboard.html` and
  `receptor_profile.html`. A filter applied in one view MUST produce the same
  subset of data when the equivalent filter is applied in the other.
- **Group metadata**: Any new API group MUST be added to `API_GROUPS` first.
  The router's `/api/of/api-groups` and `/api/of/brand-colors` endpoints are
  the single source of truth consumed by the frontend at boot.
- **Loading states and error messages**: Charts MUST display a visible loading
  indicator during fetch and a human-readable error message (not a raw HTTP
  status code) on failure.
- **Responsive baseline**: All pages MUST remain usable at 1280 × 800 viewport
  without horizontal scroll.

**Rationale**: Users switch between Ecossistema (dashboard.html) and Perfil
Receptor views frequently. Inconsistent filters or colors break their mental
model and erode trust in the data.

### IV. Performance Requirements

- **Dashboard API response time**: All `/api/of/*` endpoints MUST return within
  500 ms at p95 for the default date range (last 4 weeks, all receptors) when
  served from Cloud Run with the SQLite DB already downloaded.
- **Pre-aggregation pattern**: Any query that aggregates across more than one
  dimension (group × receptor × week) MUST use the `api_group_weekly` table
  or an equivalent pre-aggregated table. Ad-hoc multi-join aggregations in hot
  API paths are PROHIBITED. New aggregation tables MUST be populated by a
  dedicated `scrapers.refresh_*` function called at the end of each collection
  run.
- **Collection efficiency**: The hierarchical probe strategy
  (receptor → transmitter → api → combo) MUST be preserved. Any new
  collection path MUST implement the same three-level pruning before the full
  `fetch_api_combo()` call. Skipping pruning levels requires explicit
  justification documented in the PR.
- **Parallel workers**: The default `DEFAULT_WORKERS=4` (configurable via
  `.env`) MUST not be exceeded without measuring GCS/OpF API rate-limit impact.
  Worker count changes MUST be tested with `python main.py status` output
  before merging.
- **DB sync**: `sync_to_gcs.py` MUST complete in under 30 seconds for the
  current DB size. If the DB exceeds 200 MB, a compaction/archival strategy
  MUST be proposed before continuing to upload the full file.

**Rationale**: Cloud Run cold-start downloads the DB from GCS on each new
instance. Slow queries compound the cold-start penalty and degrade perceived
dashboard responsiveness.

### V. Implementation Paradigm

The system is composed of exactly two independent components; this boundary is
NON-NEGOTIABLE:

- **data-loader/** — runs locally (or scheduled via Task Scheduler / cron).
  Owns: Playwright browser session, OpFSession HTTP layer, SQLite writes,
  GCS sync. MUST NOT import anything from `dashboard/`.
- **dashboard/** — stateless Cloud Run service. Owns: FastAPI routes, SQLite
  reads, Chart.js frontend. MUST NOT import anything from `data-loader/` and
  MUST NOT write to the DB.
- **Shared state**: The single SQLite file (`consents.db`) is the only
  integration point. Schema changes MUST be backward-compatible (additive only)
  unless a coordinated migration plan is documented and both components are
  updated atomically.
- **No ORM**: Direct SQL via `sqlite3` standard library MUST be used in both
  components. ORM frameworks are PROHIBITED. SQL queries MUST be parameterized
  (no f-string interpolation of user-supplied values).
- **Configuration resolution**: `OPF_DB_PATH` env var overrides the auto-detect
  chain. New config values MUST follow the same pattern: env var → sensible
  local default → Cloud Run default. Hard-coded paths in source code are
  PROHIBITED.
- **Separate venvs**: `data-loader/` and `dashboard/` each maintain their own
  `requirements.txt` and `.venv`. Cross-component `pip install` instructions
  are a bug, not a feature.

**Rationale**: Keeping the components independently deployable ensures that a
failed collection run cannot affect the running dashboard, and that the
dashboard can be redeployed without touching collection logic.

## Stack Constraints

The following technology choices are fixed for the life of this project. Changes
require a constitution amendment:

| Layer | Constraint |
|---|---|
| Language | Python 3.11+ (both components) |
| Browser automation | Playwright + Chromium only |
| Database | SQLite via `sqlite3` stdlib — no PostgreSQL, no external DB |
| Cloud storage | Google Cloud Storage (`google-cloud-storage` SDK) |
| Deployment | Google Cloud Run (dashboard only) |
| API framework | FastAPI + Uvicorn (dashboard) |
| Frontend charting | Chart.js (no D3, no Plotly, no React) |
| Frontend build | Vanilla JS + HTML — no bundler, no TypeScript transpilation |
| Retry policy | `tenacity` library for HTTP retries in data-loader |

## Development Workflow

- **Local dev cycle**: `cd dashboard && uvicorn server:app --reload --port 8000`
  reads the DB auto-detected at `../data-loader/data/consents.db`. This path
  MUST remain the default; do not change it without updating `dashboard/config.py`.
- **Full deploy cycle**: `.\deploy.ps1` (sync + build + push + deploy). The
  `-SkipSync` and `-SyncOnly` flags MUST be preserved for incremental workflows.
- **Feature branches**: Every new feature MUST be developed on a branch named
  `<sequential-number>-<kebab-description>` (e.g., `017-payment-initiation`).
  Direct commits to `main` are PROHIBITED.
- **PR merge gate**: A PR MUST NOT be merged if it (a) leaves any bracketed
  placeholder tokens in spec/plan/tasks artifacts, (b) breaks an existing API
  endpoint shape, or (c) removes a `refresh_*` pre-aggregation call from the
  collection pipeline.
- **Commit message style**: `<type>: <imperative summary> (#<issue>)` where
  type ∈ {feat, fix, docs, refactor, test, chore}. Body optional.

## Governance

This constitution supersedes all conflicting practices documented elsewhere
(README, inline comments, verbal agreements). Conflicts are resolved in favor
of the constitution.

**Amendment procedure**:
1. Open a PR with the proposed constitution change and a `docs: amend
   constitution` commit.
2. Bump the version according to semantic versioning rules defined in the Sync
   Impact Report header (MAJOR/MINOR/PATCH).
3. Update all dependent templates whose Constitution Check gates reference the
   changed principle.
4. The PR description MUST include the Sync Impact Report.

**Compliance review**: Every PR review MUST include a Constitution Check
verifying that the diff does not violate Principles I–V. The check is not
optional even for "small" changes.

**Versioning policy**:
- MAJOR: Principle removed, renamed, or redefined in a backward-incompatible way.
- MINOR: New principle added or a section materially expanded.
- PATCH: Wording clarification, typo fix, non-semantic refinement.

**Runtime guidance**: See `CLAUDE.md` at the repository root for agent-specific
development guidance (commands, architecture diagrams, SQL schema reference).

**Version**: 1.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-05-18
