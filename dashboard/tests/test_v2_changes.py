"""
test_v2_changes.py — Dashboard 2.0 (feature 011): GET /api/v2/changes (aba "O que mudou?").

Constitution II: HTTP-level tests against the real FastAPI app with a real SQLite
file; caminho feliz, filtros, tabela ausente e parâmetros inválidos.
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from tests import v2_fixtures as F  # noqa: E402


@pytest.fixture(scope="module")
def db_full(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2c") / "full.db")


@pytest.fixture(scope="module")
def db_no_signals(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2c") / "no_signals.db", with_signals=False)


@pytest.fixture(scope="module")
def db_old(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2c") / "old.db", with_status_table=False)


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture(scope="module")
async def client(db_full: Path, monkeypatch_module):
    import config
    monkeypatch_module.setattr(config, "DB_PATH", db_full)
    import importlib
    import server
    importlib.reload(server)
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        yield c


@pytest.fixture
def use_db(monkeypatch):
    import config
    return lambda path: monkeypatch.setattr(config, "DB_PATH", path)


def _names(d):
    return [e["name"] for e in d["events"]]


@pytest.mark.asyncio
async def test_default_month_events_summary_and_order(client):
    r = await client.get("/api/v2/changes")
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == "2026-08"
    # quedas pela maior variação, depois oscilações, depois novos entrantes
    assert _names(d) == ["Nubank", "Belvo", "Santander", "Shopee"]
    assert [e["kind"] for e in d["events"]] == ["decrease", "decrease", "oscillation", "new_entrant"]
    assert d["summary"] == {"alerts": 6, "institutions": 4, "watching": 1,
                            "by_kind": {"decrease": 2, "oscillation": 1, "new_entrant": 1}}
    nu = d["events"][0]
    assert nu["max_abs_change"] == pytest.approx(0.81)
    assert [i["api_group_label"] for i in nu["items"]] == ["Cadastro", "Contas"]
    assert d["rules"] and d["computed_at"] == "2026-09-23T10:00:00Z"


@pytest.mark.asyncio
async def test_months_bar_has_twelve_months_with_counts_by_type(client):
    d = (await client.get("/api/v2/changes")).json()
    months = d["months"]
    assert len(months) == 12 and months[0]["month"] == "2025-09" and months[-1]["month"] == "2026-08"
    assert months[-1] == {"month": "2026-08", "decrease": 4, "increase": 1, "new_entrant": 1}
    assert next(m for m in months if m["month"] == "2026-07")["decrease"] == 1


@pytest.mark.asyncio
async def test_oscillation_keeps_both_alerts_in_one_event(client):
    d = (await client.get("/api/v2/changes", params={"types": "oscillation"})).json()
    assert _names(d) == ["Santander"]
    items = d["events"][0]["items"]
    assert [(i["signal_type"], i["oscillation"]) for i in items] == [("decrease", True), ("increase", True)]
    assert d["summary"]["alerts"] == 2


@pytest.mark.asyncio
async def test_months_bar_follows_type_filter(client):
    d = (await client.get("/api/v2/changes", params={"types": "oscillation"})).json()
    aug = next(m for m in d["months"] if m["month"] == "2026-08")
    assert aug == {"month": "2026-08", "decrease": 1, "increase": 1, "new_entrant": 0}
    assert next(m for m in d["months"] if m["month"] == "2026-07")["decrease"] == 0

    d = (await client.get("/api/v2/changes", params={"types": "decrease"})).json()
    aug = next(m for m in d["months"] if m["month"] == "2026-08")
    assert aug == {"month": "2026-08", "decrease": 3, "increase": 0, "new_entrant": 0}   # Nubank 2 + Belvo 1


@pytest.mark.asyncio
async def test_streak_marks_consecutive_months_with_previous_summary(client):
    d = (await client.get("/api/v2/changes")).json()
    belvo = next(e for e in d["events"] if e["name"] == "Belvo")
    assert belvo["streak_months"] == 2
    assert [(i["week"], i["api_group_label"]) for i in belvo["previous_month_summary"]] == [("2026-07-31", "Empréstimos")]
    nu = next(e for e in d["events"] if e["name"] == "Nubank")
    assert nu["streak_months"] == 1 and nu["previous_month_summary"] is None


@pytest.mark.asyncio
async def test_watching_comes_from_behavior_watch(client):
    d = (await client.get("/api/v2/changes")).json()
    assert d["watching"] == [{
        "uuid": "rec-klavi", "name": "Klavi", "group": "itps", "direction": "decrease",
        "api_group": "Investimento", "api_group_label": "Investimentos",
        "value_prev": pytest.approx(116.2e6), "value_curr": pytest.approx(68.2e6),
        "change_pct": pytest.approx(-0.44), "week": "2026-08-28", "confirm_week": "2026-09-04"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("params, expected", [
    ({"signal": "api"}, ["Nubank", "Belvo"]),
    ({"signal": "consents"}, ["Santander", "Shopee"]),
    ({"institution": "NUBÂNK"}, ["Nubank"]),
    ({"groups": "outros"}, ["Shopee"]),
    ({"types": "new_entrant,oscillation"}, ["Santander", "Shopee"]),
    ({"month": "2026-07"}, ["Belvo"]),
    ({"month": "2026-05"}, []),
])
async def test_filters(client, params, expected):
    d = (await client.get("/api/v2/changes", params=params)).json()
    assert _names(d) == expected


@pytest.mark.asyncio
async def test_signal_consents_hides_watch(client):
    d = (await client.get("/api/v2/changes", params={"signal": "consents"})).json()
    assert d["watching"] == []


@pytest.mark.asyncio
async def test_missing_signals_table_is_unavailable_not_error(client, use_db, db_no_signals):
    use_db(db_no_signals)
    r = await client.get("/api/v2/changes")
    assert r.status_code == 200
    assert r.json()["unavailable"] == ["signals"] and r.json()["events"] == []


@pytest.mark.asyncio
async def test_old_base_without_watch_table_still_lists_events(client, use_db, db_old):
    use_db(db_old)
    d = (await client.get("/api/v2/changes")).json()
    assert len(d["events"]) == 4 and d["watching"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"month": "2026-13"}, {"month": "agosto"}, {"types": "foo"}, {"signal": "x"}])
async def test_invalid_params_are_422(client, params):
    r = await client.get("/api/v2/changes", params=params)
    assert r.status_code == 422 and r.json()["detail"]
