<!--
SYNC IMPACT REPORT
==================
Version change: 1.5.0 → 2.0.0
Bump type: MAJOR — a UI principle is removed: the legacy shell (Principle VI §6.1–6.7) and
the rules that existed only for the v1 pages.

Modified principles:
  Principle III: colors come from `API_GROUPS` and `GROUP_COLORS_V2` only (no `GROUP_COLORS`);
    group metadata is served by `GET /api/v2/meta`; the loading indicator is `.v2-card.loading`;
    filter persistence is only `opf:v2:filters`.
  Principle VI: §6.1–6.7 (DOM skeleton, titlebar, sidebar, date bar, design tokens, chart
    cards, theme toggle of the legacy pages) removed. §6.8 Shell v2 is the only shell; the
    header no longer carries the "Painel atual (legado)" link. The number §6.8 is kept.
    Why: the v1 pages (`/`, `/profile`, `/active-consents`) were removed in feature 016; `/`,
    `/profile` and `/active-consents` now redirect to `/v2`.
    Decided by the product owner on 2026-11-19.

Templates reviewed: plan-template.md gate for VI refers to "which shell applies" (single shell now).
Follow-up TODOs: none.

Previous report (1.4.0 → 1.5.0)
-------------------------------
Version change: 1.4.0 → 1.5.0
Bump type: MINOR — Shell v2 gains an unlisted page and an exception to the "Exportar CSV" rule
(Principle VI §6.8 "Pages and tab order", "Export").

Modified principles:
  Principle VI §6.8:
    - "Pages and tab order": `Exportar dados` → `/v2/exportar` (feature 015) is a v2 page that is
      NOT a tab: it is not listed in the header and is reachable only by its URL. The four
      tabs stay as they were.
    - "Export": `/v2/exportar` is exempt from the filter-bar "Exportar CSV" button. Its
      export button lives in the "Resumo" card (and in a fixed bar on narrow screens), because
      the whole page is the export. Access is restricted by a fixed code checked only on the server
      (`EXPORT_CODE` in `services/export.py`); the other tabs stay public.
    Why: the product owner asked for a new tab where users pick the collected tables and
    filters and download the data (no collection logs, no derived analyses).
    Decided by the product owner on 2026-11-19.

Templates reviewed: no template change.
Follow-up TODOs: none.

Previous report (1.3.0 → 1.4.0)
-------------------------------
Version change: 1.3.0 → 1.4.0
Bump type: MINOR — one Shell v2 rule extended (Principle VI §6.8 "Export").

Modified principles:
  Principle VI §6.8:
    - "Export": besides the per-block image and the single "Exportar CSV", a page may offer
      one "Exportar slide" in the filter bar, next to "Exportar CSV": a 1600×900 PNG that
      composes the page's blocks in the same frame as the block images (title with active
      filters, source footer), without reducing text below the minimum (lists that do not fit
      are cut to the largest items with "+N"). First use: /v2/instituicao (feature 014),
      without the alerts, the API error rate and the by-group calls.
    Why: a profile slide used to be assembled by hand from several block images.
    Decided by the product owner on 2026-10-30.

Templates reviewed: no template change.
Follow-up TODOs: none.

Previous report (1.2.0 → 1.3.0)
-------------------------------
Version change: 1.2.0 → 1.3.0
Bump type: MINOR — material change to two Shell v2 rules (Principle VI §6.8).

Modified principles:
  Principle VI §6.8:
    - "Cards": the "Copiar como imagem" action belongs to every content block (a
      `.v2-card` with an `h2`); indicator cards (KPIs, top answers, group summaries)
      carry no actions. "Baixar CSV" is no longer required on every card.
    - "Export": CSV is one "Exportar CSV" button per page, in the filter bar, right-aligned
      and with the same label on every tab; blocks that already export their own CSV
      (rankings, monthly alerts) keep that icon.
    Why: only 3 of ~20 blocks had both actions, and each page's global CSV already
    covers the data; implementing ~15 more block exporters would be redundant.
    Decided by the product owner on 2026-10-30.

Templates reviewed: no template change (plan/spec/tasks templates do not mention card actions).
Follow-up TODOs: none.

Previous report (1.1.0 → 1.2.0)
-------------------------------
Version change: 1.1.0 → 1.2.0
Bump type: MINOR — new section added (Principle VI §6.8 "Shell v2") and Stack
table expanded. The existing shell contract (§6.1–6.7) is unchanged and now
applies explicitly to the legacy pages.

Modified principles:
  Principle III: color rule extended to institution-group palettes
    (GROUP_COLORS for legacy, GROUP_COLORS_V2 for Dashboard 2.0); filter
    persistence rule now per shell (legacy `opf:filters`, v2 `opf:v2:*`);
    rationale no longer names the three legacy tabs only.
  Principle VI: §6.1–6.7 scoped to legacy pages (`/`, `/profile`,
    `/active-consents`); legacy titlebar may carry a "Dashboard 2.0" link;
    new §6.8 Shell v2 for `/v2*` pages (feature 011-dashboard-v2).

Added sections:
  - Principle VI §6.8 Shell v2
  - Stack Constraints row: image export (frontend) = html-to-image

Templates reviewed:
  ✅ plan-template.md — VI gate now asks which shell (legacy or v2) applies.
  ✅ spec-template.md / tasks-template.md — no structural change.

Follow-up TODOs:
  - Implement Shell v2 (specs/011-dashboard-v2).

Previous report (1.0.0 → 1.1.0)
-------------------------------
Bump type: MINOR — new principle added (VI: UI Shell Contract).

Modified principles:
  Principle III expanded: added explicit reference to Principle VI for shell
  structure (cross-reference only; no semantic change to III).

Added sections:
  - Principle VI: UI Shell Contract (new)
  - Shell Contract reference table in Principle III

Removed sections:
  - None

Templates reviewed:
  ✅ .specify/templates/plan-template.md — Constitution Check gates should
     now include a VI-gate: "Does this feature touch a dashboard page? If so,
     does it follow the shell contract?"
  ✅ .specify/templates/spec-template.md — No structural change needed;
     acceptance criteria for UI features should reference the shell components.
  ✅ .specify/templates/tasks-template.md — No structural change needed.

Follow-up TODOs:
  - Apply shell contract to active_consents.html (feature 003-ui-shell-ativos).
  - Add Constitution Check VI gate to plan-template.md on next plan run.
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

All dashboard views MUST share a single visual and behavioral contract. The
structural shell is defined in Principle VI below; the data/behavior rules are:

- **Color palette**: All chart colors MUST be sourced from
  `dashboard/services/constants.py` — `API_GROUPS` for API groups,
  `GROUP_COLORS_V2` for institution groups. Hardcoded hex values for data series in HTML or
  JavaScript are PROHIBITED; theme tokens live in CSS variables.
- **Filter behavior**: Date range (`start`/`end`) and receptor filter
  (`receptors`) MUST behave identically across all dashboard pages. A filter
  applied in one view MUST produce the same subset of data when the equivalent
  filter is applied in another.
- **Group metadata**: Any new API group MUST be added to `API_GROUPS` first.
  `GET /api/v2/meta` is the single source of truth consumed by the frontend at
  boot.
- **Loading states and error messages**: Charts MUST display a visible loading
  indicator (`.v2-card.loading` sweep animation) during fetch and a human-readable
  error message (not a raw HTTP status code) on failure.
- **Responsive baseline**: All pages MUST remain usable at 1280 × 800 viewport
  without horizontal scroll.
- **Filter persistence**: Dashboard 2.0 pages use `sessionStorage['opf:v2:filters']`
  (see §6.8). The key MUST be read on page load and written on every filter
  change. Pages MUST only write the fields they own and MUST preserve (spread)
  existing fields from other pages.

**Rationale**: Users switch between the pages frequently. Inconsistent filters, colors, or shell structure break their mental
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

### VI. UI Shell Contract

Every dashboard page MUST implement the Shell v2 defined here. (The legacy shell,
§6.1–6.7, was removed with the v1 panel in feature 016; the number §6.8 is kept so
references in specs and history stay valid.) Deviations require an explicit amendment.

#### 6.8 Shell v2 (Dashboard 2.0 — `/v2*`)

Canonical reference: `specs/011-dashboard-v2/contracts/v2-ui-shell.md`.

- **Pages and tab order** (all four MUST appear on every v2 page):
  1. `Quem lidera?` → `/v2`
  2. `Como evolui?` → `/v2/evolucao`
  3. `O que mudou?` → `/v2/mudancas`
  4. `Como opera uma instituição?` → `/v2/instituicao`
  Unlisted: `Exportar dados` → `/v2/exportar` (feature 015) is not a tab; it is reachable only by URL
  and uses the same skeleton.
- **Skeleton**: `<header class="v2-header">` (brand · tabs with
  `aria-current` · "Dados até … · atualizado em …" · theme toggle) → `<main class="v2-main">` (max-width 1280px) →
  `.v2-filterbar` first → page title → `.v2-card` blocks. No sidebar.
- **Filter bar**: shows only the controls that apply to the open tab; any
  change reloads immediately (no "Aplicar", no "Recarregar dados").
- **Shared state**: `sessionStorage['opf:v2:filters']`; ranking preferences in
  `localStorage['opf:v2:ranking']`; theme in `localStorage['opf:v2:theme']`
  (default `light`, applied before first paint). Every storage access MUST
  tolerate unavailable storage.
- **Shared code**: header, filter state, formatting and export MUST live in
  `dashboard/gui/v2/shell.js` and `dashboard/gui/v2/v2.css`; pages contain
  only their own blocks.
- **Cards**: every content block (a `.v2-card` with an `h2`) has title, subtitle
  (metric + week), footer with rule and source, and a "Copiar como imagem" action.
  Indicator cards (KPIs, top answers, group summaries) carry no actions. Active
  filters appear in the card title.
- **Export**: PNG 1600×900 per block with title, metric, data date, active filter
  and source. CSV (`;`, decimal comma, UTF-8 BOM) is one "Exportar CSV" button per
  page, in the filter bar, right-aligned and with the same label on every tab;
  blocks that already export their own CSV (rankings, monthly alerts) keep that icon.
  A page may also offer one "Exportar slide" (PNG 1600×900) next to it, composing the page's
  blocks in the same frame; text never shrinks below the minimum (lists are cut with "+N").
  `/v2/exportar` is exempt from the filter-bar button: its export button lives in the
  "Resumo" card (a fixed bottom bar below 720 px), and it needs an access code.
- **Loading/errors**: visible loading state per card and human-readable error
  messages, as in Principle III.

**Rationale**: The Dashboard 2.0 pages share a single user mental model. Diverging
in shell structure — even partially —
creates a perception of instability and makes onboarding new users harder. The
shell contract is the minimum unit of visual consistency that must be maintained
across all future pages.

---

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
| Image export (frontend) | `html-to-image` (CDN), Dashboard 2.0 only |
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

**Version**: 2.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-11-19
