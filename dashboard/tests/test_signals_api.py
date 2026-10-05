"""
test_signals_api.py — HTTP-level tests for GET /api/signals (feature 010).

Constitution II: each new FastAPI endpoint needs HTTP-level tests covering the happy
path and error/empty cases. Uses httpx.AsyncClient against the real app with a tmp
SQLite DB, mirroring test_institution_groups.py.
"""

import sqlite3
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

W_OLD  = "2026-07-24"
W_MAIN = "2026-07-31"
W_DATA = "2026-08-07"   # última semana com dados, sem nenhum alerta

# (week, signal_type, metric, api_group, receptor_uuid, receptor, prev, curr, pct, volume)
SIGNAL_ROWS = [
    (W_OLD,  "new_entrant", "unique_consents", "",        "u-inter", "Banco Inter S.A.",    None,      40_000,   None,  40_000),
    (W_MAIN, "decrease",    "api_group",       "Cartao",  "u-safra", "Banco Safra S.A.",    2_100_000, 810_000,  -0.61, 26_427),
    (W_MAIN, "decrease",    "api_group",       "Credito", "u-safra", "Banco Safra S.A.",    1_900_000, 820_000,  -0.57, 26_427),
    (W_MAIN, "decrease",    "unique_consents", "",        "u-csf",   "Banco CSF S/A",       101_702,   17_404,   -0.83, 17_404),
    (W_MAIN, "increase",    "api_group",       "Conta",   "u-cw",    "CloudWalk",           1_200_000, 5_200_000, 3.36, 200_000),
    (W_MAIN, "increase",    "unique_consents", "",        "u-brad",  "Banco Bradesco S.A.", 750_000,   900_000,  0.20,  900_000),
]


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("db") / "test_signals.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE unique_consents (receptor_uuid TEXT, receptor TEXT, date TEXT,
                                      total INTEGER, cpf INTEGER, cnpj INTEGER);
        CREATE TABLE active_consents (receptor_uuid TEXT, transmitter_uuid TEXT, receptor TEXT,
                                      transmitter TEXT, date TEXT, total INTEGER, fetched_at TEXT);
        CREATE TABLE api_requests (receptor_uuid TEXT, receptor TEXT, transmitter_uuid TEXT,
                                   transmitter TEXT, api TEXT, endpoint_id INTEGER, endpoint TEXT,
                                   status INTEGER, date TEXT, total INTEGER);
        CREATE TABLE api_group_weekly (date TEXT, receptor_uuid TEXT, receptor TEXT, grp TEXT,
                                       req_week INTEGER, consents_total INTEGER);
        CREATE TABLE fetch_attempts (run_id TEXT, phase TEXT, target TEXT, started_at TEXT,
                                     duration_ms INTEGER, status TEXT, records_count INTEGER,
                                     error_class TEXT, error_msg TEXT);
        CREATE TABLE run_summary (run_id TEXT PRIMARY KEY);
        CREATE TABLE behavior_signals (
            week TEXT NOT NULL, signal_type TEXT NOT NULL, metric TEXT NOT NULL,
            api_group TEXT NOT NULL DEFAULT '', receptor_uuid TEXT NOT NULL,
            receptor TEXT NOT NULL DEFAULT '', value_prev REAL, value_curr REAL NOT NULL,
            change_pct REAL, volume INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (week, signal_type, metric, api_group, receptor_uuid));
        CREATE TABLE behavior_signals_run (
            id INTEGER PRIMARY KEY CHECK (id = 1), computed_at TEXT NOT NULL,
            consents_through TEXT, api_through TEXT,
            api_skipped_weeks TEXT NOT NULL DEFAULT '[]', signals_total INTEGER NOT NULL DEFAULT 0);
    """)
    con.executemany("INSERT INTO behavior_signals VALUES (?,?,?,?,?,?,?,?,?,?)", SIGNAL_ROWS)
    con.execute("INSERT INTO behavior_signals_run VALUES (1, '2026-09-23T11:00:00Z', ?, ?, ?, ?)",
                (W_DATA, W_DATA, f'["{W_OLD}"]', len(SIGNAL_ROWS)))
    con.commit()
    con.close()
    return p


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture(scope="module")
async def client(db_path: Path, monkeypatch_module):
    import config
    monkeypatch_module.setattr(config, "DB_PATH", db_path)
    import importlib
    import server
    importlib.reload(server)
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        yield c


def _names(section):
    return [e["receptor"] for e in section]


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_week_is_latest_data_week_even_without_alerts(client):
    r = await client.get("/api/signals")
    assert r.status_code == 200
    d = r.json()
    assert d["week"] == W_DATA
    assert d["sections"] == {"new_entrant": [], "increase": [], "decrease": []}
    assert [w["week"] for w in d["weeks"]] == [W_MAIN, W_OLD]
    assert d["computed_at"] == "2026-09-23T11:00:00Z"


@pytest.mark.asyncio
async def test_week_groups_by_institution_and_orders_by_volume(client):
    d = (await client.get(f"/api/signals?week={W_MAIN}")).json()
    assert set(d["sections"]) == {"new_entrant", "increase", "decrease"}
    # Safra tem dois alertas de API na semana → uma única entrada com dois itens
    assert _names(d["sections"]["decrease"]) == ["Banco Safra S.A.", "Banco CSF S/A"]
    safra = d["sections"]["decrease"][0]
    assert [i["api_group"] for i in safra["items"]] == ["Cartao", "Credito"]
    assert _names(d["sections"]["increase"]) == ["Banco Bradesco S.A.", "CloudWalk"]
    assert d["sections"]["increase"][0]["institution_group"] == "incumbentes"
    assert d["sections"]["decrease"][1]["items"][0]["api_group"] is None


@pytest.mark.asyncio
async def test_groups_filter_applies_to_sections_and_week_list(client):
    d = (await client.get(f"/api/signals?week={W_MAIN}&groups=incumbentes")).json()
    assert _names(d["sections"]["increase"]) == ["Banco Bradesco S.A."]
    assert d["sections"]["decrease"] == []
    assert d["weeks"] == [{"week": W_MAIN, "count": 1}]


@pytest.mark.asyncio
async def test_api_incomplete_flag_for_blocked_week(client):
    d_old = (await client.get(f"/api/signals?week={W_OLD}")).json()
    d_main = (await client.get(f"/api/signals?week={W_MAIN}")).json()
    assert d_old["api_incomplete"] is True
    assert d_main["api_incomplete"] is False
    assert _names(d_old["sections"]["new_entrant"]) == ["Banco Inter S.A."]


# ── Empty / error cases ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_week_returns_empty_sections_with_week_list(client):
    d = (await client.get("/api/signals?week=2020-01-03")).json()
    assert d["week"] == "2020-01-03"
    assert all(v == [] for v in d["sections"].values())
    assert len(d["weeks"]) == 2


@pytest.mark.asyncio
async def test_invalid_week_falls_back_to_default(client):
    d = (await client.get("/api/signals?week=not-a-date")).json()
    assert d["week"] == W_DATA


@pytest.mark.asyncio
async def test_missing_table_returns_empty_structure(client, tmp_path, monkeypatch):
    """Base na nuvem antes da primeira execução do compute_signals.py."""
    empty_db = tmp_path / "no_signals.db"
    sqlite3.connect(str(empty_db)).close()
    import config
    monkeypatch.setattr(config, "DB_PATH", empty_db)

    r = await client.get("/api/signals")
    assert r.status_code == 200
    d = r.json()
    assert d["weeks"] == [] and d["computed_at"] is None
    assert all(v == [] for v in d["sections"].values())
    # o dashboard não pode ter criado a tabela
    tables = {t for (t,) in sqlite3.connect(str(empty_db)).execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "behavior_signals" not in tables
