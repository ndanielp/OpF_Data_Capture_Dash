"""
test_active_consents_api.py — HTTP-level tests for /api/active-consents/* endpoints.

Constitution II: each new FastAPI endpoint must have at least one HTTP-level test
covering the happy path and one error/empty case.

Uses httpx.AsyncClient against the real FastAPI app with a tmp SQLite DB.
"""

import sqlite3
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Path setup ───────────────────────────────────────────────────────────────
_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

# ── Test data constants ───────────────────────────────────────────────────────
DATE_CURR = "2026-05-19"
DATE_PREV = "2026-05-12"

RECEPTORS = [
    ("rec-uuid-001", "Banco Bradesco S.A."),
    ("rec-uuid-002", "Banco do Brasil S.A."),
]
TRANSMITTERS = [
    ("txm-uuid-AAA", "99PAY S.A."),
    ("txm-uuid-BBB", "Itaú Unibanco S.A."),
    ("txm-uuid-CCC", "Nubank S.A."),
]

# active_consents rows: (receptor_uuid, transmitter_uuid, receptor, transmitter, date, total)
ACTIVE_ROWS_CURR = [
    ("rec-uuid-001", "txm-uuid-AAA", "Banco Bradesco S.A.", "99PAY S.A.",         DATE_CURR, 1200),
    ("rec-uuid-001", "txm-uuid-BBB", "Banco Bradesco S.A.", "Itaú Unibanco S.A.", DATE_CURR,  800),
    ("rec-uuid-001", "txm-uuid-CCC", "Banco Bradesco S.A.", "Nubank S.A.",        DATE_CURR,  300),
    ("rec-uuid-002", "txm-uuid-AAA", "Banco do Brasil S.A.", "99PAY S.A.",        DATE_CURR,  500),
    ("rec-uuid-002", "txm-uuid-BBB", "Banco do Brasil S.A.", "Itaú Unibanco S.A.",DATE_CURR,  200),
]
ACTIVE_ROWS_PREV = [
    ("rec-uuid-001", "txm-uuid-AAA", "Banco Bradesco S.A.", "99PAY S.A.",         DATE_PREV, 1000),
    ("rec-uuid-001", "txm-uuid-BBB", "Banco Bradesco S.A.", "Itaú Unibanco S.A.", DATE_PREV,  700),
    ("rec-uuid-002", "txm-uuid-AAA", "Banco do Brasil S.A.", "99PAY S.A.",        DATE_PREV,  400),
]
# unique_consents rows: (receptor_uuid, receptor, date, total, cpf, cnpj)
UNIQUE_ROWS = [
    ("rec-uuid-001", "Banco Bradesco S.A.", DATE_CURR, 2300, 2100, 200),
    ("rec-uuid-002", "Banco do Brasil S.A.", DATE_CURR,  700,  600, 100),
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    """Real SQLite DB with test data, shared across all tests in this module."""
    p = tmp_path_factory.mktemp("db") / "test_consents.db"
    con = sqlite3.connect(str(p))

    con.executescript("""
        CREATE TABLE IF NOT EXISTS active_consents (
            receptor_uuid    TEXT NOT NULL,
            transmitter_uuid TEXT NOT NULL,
            receptor         TEXT NOT NULL DEFAULT '',
            transmitter      TEXT NOT NULL DEFAULT '',
            date             TEXT NOT NULL,
            total            INTEGER NOT NULL,
            fetched_at       TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (receptor_uuid, transmitter_uuid, date)
        );
        CREATE TABLE IF NOT EXISTS unique_consents (
            receptor_uuid TEXT NOT NULL,
            receptor      TEXT NOT NULL DEFAULT '',
            date          TEXT NOT NULL,
            total         INTEGER NOT NULL DEFAULT 0,
            cpf           INTEGER NOT NULL DEFAULT 0,
            cnpj          INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (receptor_uuid, date)
        );
        CREATE TABLE IF NOT EXISTS api_group_weekly (
            date           TEXT    NOT NULL,
            receptor_uuid  TEXT    NOT NULL,
            receptor       TEXT    NOT NULL DEFAULT '',
            grp            TEXT    NOT NULL,
            req_week       INTEGER NOT NULL DEFAULT 0,
            consents_total INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, receptor_uuid, grp)
        );
        CREATE TABLE IF NOT EXISTS api_requests (
            receptor_uuid TEXT, receptor TEXT, transmitter_uuid TEXT, transmitter TEXT,
            api TEXT, endpoint_id INTEGER, endpoint TEXT, status INTEGER,
            date TEXT, total INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS fetch_attempts (
            run_id TEXT, phase TEXT, target TEXT, started_at TEXT,
            duration_ms INTEGER, status TEXT, records_count INTEGER,
            error_class TEXT, error_msg TEXT
        );
        CREATE TABLE IF NOT EXISTS run_summary (
            run_id TEXT PRIMARY KEY
        );
    """)

    con.executemany(
        "INSERT OR REPLACE INTO active_consents "
        "(receptor_uuid, transmitter_uuid, receptor, transmitter, date, total) VALUES (?,?,?,?,?,?)",
        ACTIVE_ROWS_CURR + ACTIVE_ROWS_PREV,
    )
    con.executemany(
        "INSERT OR REPLACE INTO unique_consents "
        "(receptor_uuid, receptor, date, total, cpf, cnpj) VALUES (?,?,?,?,?,?)",
        UNIQUE_ROWS,
    )
    con.commit()
    con.close()
    return p


@pytest.fixture(scope="module")
def override_config(db_path: Path, monkeypatch_module):
    """Patch config.DB_PATH to point to the test DB."""
    import config
    monkeypatch_module.setattr(config, "DB_PATH", db_path)


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped monkeypatch."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture(scope="module")
async def client(db_path: Path, monkeypatch_module):
    """AsyncClient with DB override, shared across all tests."""
    import config
    monkeypatch_module.setattr(config, "DB_PATH", db_path)

    # Re-import server after patching config so DB_PATH is used
    import importlib
    import server
    importlib.reload(server)

    async with AsyncClient(
        transport=ASGITransport(app=server.app),
        base_url="http://test",
    ) as c:
        yield c


# ── Smoke test ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_server_healthy(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_active_consents_page(client: AsyncClient):
    r = await client.get("/active-consents")
    assert r.status_code == 200
    assert "Consentimentos Ativos" in r.text


# ── /evolution ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evolution_by_receptor_shape(client: AsyncClient):
    r = await client.get(f"/api/active-consents/evolution?start={DATE_PREV}&end={DATE_CURR}&by=receptor")
    assert r.status_code == 200
    d = r.json()
    assert d["by"] == "receptor"
    assert len(d["labels"]) >= 1
    assert len(d["series"]) >= 1
    # Each series values length matches labels length
    for s in d["series"]:
        assert len(s["values"]) == len(d["labels"])

@pytest.mark.asyncio
async def test_evolution_by_transmitter(client: AsyncClient):
    r = await client.get(f"/api/active-consents/evolution?start={DATE_PREV}&end={DATE_CURR}&by=transmitter")
    assert r.status_code == 200
    d = r.json()
    assert d["by"] == "transmitter"
    assert len(d["series"]) >= 1

@pytest.mark.asyncio
async def test_evolution_empty_period(client: AsyncClient):
    r = await client.get("/api/active-consents/evolution?start=2000-01-01&end=2000-01-07")
    assert r.status_code == 200
    d = r.json()
    assert d["series"] == []
    assert d["labels"] == []

@pytest.mark.asyncio
async def test_evolution_receptor_filter(client: AsyncClient):
    r = await client.get(
        f"/api/active-consents/evolution?start={DATE_PREV}&end={DATE_CURR}"
        f"&by=receptor&receptors=Bradesco"
    )
    assert r.status_code == 200
    d = r.json()
    # Only Bradesco-matching series should appear
    for s in d["series"]:
        assert "bradesco" in s["name"].lower()

@pytest.mark.asyncio
async def test_evolution_values_sum_correct(client: AsyncClient):
    """Bradesco total on DATE_CURR should be 1200+800+300 = 2300."""
    r = await client.get(
        f"/api/active-consents/evolution?start={DATE_CURR}&end={DATE_CURR}"
        f"&by=receptor&receptors=Bradesco"
    )
    d = r.json()
    assert d["labels"] == [DATE_CURR]
    bradesco = next(s for s in d["series"] if "bradesco" in s["name"].lower())
    assert bradesco["values"][0] == 2300


# ── /matrix ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_matrix_shape(client: AsyncClient):
    r = await client.get(f"/api/active-consents/matrix?end={DATE_CURR}")
    assert r.status_code == 200
    d = r.json()
    assert len(d["receptors"]) == 2
    assert len(d["transmitters"]) >= 2
    assert len(d["values"]) == len(d["receptors"])
    assert len(d["values"][0]) == len(d["transmitters"])

@pytest.mark.asyncio
async def test_matrix_reference_date(client: AsyncClient):
    r = await client.get(f"/api/active-consents/matrix?end={DATE_CURR}")
    d = r.json()
    assert d["reference_date"] == DATE_CURR

@pytest.mark.asyncio
async def test_matrix_no_data(client: AsyncClient):
    r = await client.get("/api/active-consents/matrix?end=2000-01-01")
    assert r.status_code == 200
    d = r.json()
    assert d["receptors"] == []
    assert d["values"] == []

@pytest.mark.asyncio
async def test_matrix_receptor_filter(client: AsyncClient):
    r = await client.get(f"/api/active-consents/matrix?end={DATE_CURR}&receptors=Bradesco")
    d = r.json()
    assert len(d["receptors"]) == 1
    assert "bradesco" in d["receptors"][0].lower()

@pytest.mark.asyncio
async def test_matrix_max_value(client: AsyncClient):
    """max_value should be 1200 (Bradesco × 99PAY on DATE_CURR)."""
    r = await client.get(f"/api/active-consents/matrix?end={DATE_CURR}")
    d = r.json()
    assert d["max_value"] == 1200


# ── /ranking ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ranking_receptor_ordered(client: AsyncClient):
    r = await client.get(f"/api/active-consents/ranking?end={DATE_CURR}&by=receptor")
    assert r.status_code == 200
    d = r.json()
    totals = [i["total"] for i in d["items"]]
    assert totals == sorted(totals, reverse=True)

@pytest.mark.asyncio
async def test_ranking_transmitter(client: AsyncClient):
    r = await client.get(f"/api/active-consents/ranking?end={DATE_CURR}&by=transmitter")
    assert r.status_code == 200
    d = r.json()
    assert d["by"] == "transmitter"
    assert len(d["items"]) >= 1

@pytest.mark.asyncio
async def test_ranking_delta_pct_correct(client: AsyncClient):
    """Bradesco: prev=1000+700=1700, curr=1200+800+300=2300 → Δ%=(2300-1700)/1700*100=35.3"""
    r = await client.get(f"/api/active-consents/ranking?end={DATE_CURR}&by=receptor")
    d = r.json()
    bradesco = next((i for i in d["items"] if "bradesco" in i["name"].lower()), None)
    assert bradesco is not None
    assert bradesco["total"] == 2300
    assert bradesco["total_prev"] == 1700
    assert bradesco["delta_pct"] == pytest.approx(35.3, abs=0.2)

@pytest.mark.asyncio
async def test_ranking_no_prev_week(client: AsyncClient):
    """When only one week exists, delta_pct and prev_date should be None."""
    r = await client.get(f"/api/active-consents/ranking?end={DATE_PREV}&by=receptor")
    d = r.json()
    assert d["prev_date"] is None
    for item in d["items"]:
        assert item["delta_pct"] is None

@pytest.mark.asyncio
async def test_ranking_limit(client: AsyncClient):
    r = await client.get(f"/api/active-consents/ranking?end={DATE_CURR}&by=receptor&limit=1")
    d = r.json()
    assert len(d["items"]) <= 1

@pytest.mark.asyncio
async def test_ranking_no_data(client: AsyncClient):
    r = await client.get("/api/active-consents/ranking?end=2000-01-01")
    assert r.status_code == 200
    d = r.json()
    assert d["items"] == []


# ── /intensity ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intensity_correct_value(client: AsyncClient):
    """Bradesco: 2300 ativos ÷ 2300 únicos = 1.0; Brasil: 700 ÷ 700 = 1.0."""
    r = await client.get(f"/api/active-consents/intensity?end={DATE_CURR}")
    assert r.status_code == 200
    d = r.json()
    bradesco = next((i for i in d["items"] if "bradesco" in i["receptor"].lower()), None)
    assert bradesco is not None
    assert bradesco["active_total"] == 2300
    assert bradesco["unique_total"] == 2300
    assert bradesco["intensity"] == pytest.approx(1.0, abs=0.1)

@pytest.mark.asyncio
async def test_intensity_reference_date(client: AsyncClient):
    r = await client.get(f"/api/active-consents/intensity?end={DATE_CURR}")
    d = r.json()
    assert d["reference_date"] == DATE_CURR

@pytest.mark.asyncio
async def test_intensity_null_when_no_unique(client: AsyncClient):
    """If unique_consents has no row for a receptor, intensity should be null."""
    # Insert a receptor with no unique_consents row
    import config
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute(
        "INSERT OR IGNORE INTO active_consents "
        "(receptor_uuid, transmitter_uuid, receptor, transmitter, date, total) "
        "VALUES (?,?,?,?,?,?)",
        ("rec-uuid-999", "txm-uuid-AAA", "Receptor Sem Único", "99PAY S.A.", DATE_CURR, 100),
    )
    con.commit()
    con.close()

    r = await client.get(f"/api/active-consents/intensity?end={DATE_CURR}&receptors=Sem Único")
    d = r.json()
    if d["items"]:
        assert d["items"][0]["intensity"] is None

@pytest.mark.asyncio
async def test_intensity_no_data(client: AsyncClient):
    r = await client.get("/api/active-consents/intensity?end=2000-01-01")
    assert r.status_code == 200
    d = r.json()
    assert d["items"] == []

@pytest.mark.asyncio
async def test_intensity_ordered_desc(client: AsyncClient):
    """Items should be ordered by intensity DESC (nulls last)."""
    r = await client.get(f"/api/active-consents/intensity?end={DATE_CURR}")
    d = r.json()
    non_null = [i["intensity"] for i in d["items"] if i["intensity"] is not None]
    assert non_null == sorted(non_null, reverse=True)
