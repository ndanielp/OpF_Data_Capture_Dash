"""
test_v2_meta_ranking.py — Dashboard 2.0 (feature 011): /api/v2/meta, /api/v2/ranking,
páginas /v2 e as regras puras de ritmo, crescimento e Top N.

Constitution II: HTTP-level tests against the real FastAPI app (httpx + ASGI) with a
real SQLite file; caminho feliz e erros para cada endpoint novo.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from tests import v2_fixtures as F  # noqa: E402


@pytest.fixture(scope="module")
def db_full(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2") / "v2_full.db")


@pytest.fixture(scope="module")
def db_no_status(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2") / "v2_no_status.db", with_status_table=False)


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
    """Troca a base só para um teste (o router lê config.DB_PATH a cada chamada)."""
    import config

    def _use(path: Path):
        monkeypatch.setattr(config, "DB_PATH", path)
    return _use


def _series(values, start="2026-01-02"):
    idx = pd.date_range(start, periods=len(values), freq="7D")
    return pd.Series(values, index=idx, dtype=float)


# ── Regras puras (T016) ───────────────────────────────────────────────────────

def test_pace_stock_linear_growth_is_flat():
    from services import v2_metrics as M
    s = _series([1_000_000 + 7_000 * i for i in range(12)])
    p = M.pace_stock(s, s.index[-1])
    assert p["per_day"] == pytest.approx(1_000)
    assert p["prev_per_day"] == pytest.approx(1_000)
    assert p["trend"] == "flat"


def test_pace_stock_arrow_beyond_ten_percent():
    from services import v2_metrics as M
    up = _series([100_000] * 5 + [100_000 + 7_000 * i for i in range(1, 5)] + [128_000 + 8_400 * i for i in range(1, 5)])
    assert M.pace_stock(up, up.index[-1])["trend"] == "up"
    down = _series([100_000 + 14_000 * i for i in range(9)] + [212_000 + 7_000 * i for i in range(1, 5)])
    assert M.pace_stock(down, down.index[-1])["trend"] == "down"


def test_pace_stock_missing_base_week_uses_previous_observation_and_real_days():
    from services import v2_metrics as M
    s = _series([1_000_000 + 7_000 * i for i in range(10)])
    s.iloc[-5] = float("nan")      # a semana S−4 não foi coletada
    p = M.pace_stock(s, s.index[-1])
    assert p["per_day"] == pytest.approx(1_000)     # (S − S−5) ÷ 35 dias, nunca contra zero


def test_pace_flow_compares_four_week_daily_means():
    from services import v2_metrics as M
    s = _series([700] * 4 + [770] * 4)
    p = M.pace_flow(s, s.index[-1])
    assert p["per_day"] == pytest.approx(110)
    assert p["change_pct"] == pytest.approx(0.10)
    assert p["trend"] == "flat"


def test_growth_kinds():
    from services import v2_metrics as M
    s = _series([100, 120, 150, 200])
    assert M.growth_stock(s, s.index[0], s.index[-1]) == {"kind": "pct", "value": pytest.approx(1.0), "debut_month": None}
    tiny = _series([300, 1_000, 10_000, 31_200])
    g = M.growth_stock(tiny, tiny.index[0], tiny.index[-1])
    assert g["kind"] == "multiplier" and g["value"] == pytest.approx(104)
    late = _series([float("nan"), float("nan"), 50, 80])
    g = M.growth_stock(late, late.index[0], late.index[-1])
    assert g["kind"] == "debut" and g["debut_month"] == late.index[2].strftime("%Y-%m")
    zero_base = _series([10, 0, 0, 40])
    assert M.growth_stock(zero_base, zero_base.index[1], zero_base.index[-1])["kind"] == "no_base"


def test_presence_since_first_data_week_is_not_a_debut():
    from services import v2_metrics as M
    s = _series([100, 110, 120])
    assert M.growth_stock(s, pd.Timestamp("2000-01-01"), s.index[-1])["kind"] == "pct"


def _row(uuid, value, group="outros"):
    return {"uuid": uuid, "name": uuid, "group": group, "value": value,
            "pace": None, "growth": {"kind": "pct", "value": 0.1}, "per_consent_month": None}


def test_build_ranking_exclusion_pin_and_group_filter():
    from services import v2_metrics as M
    base = lambda: [_row("a", 50, "itps"), _row("b", 40, "neo_banks"), _row("c", 30, "itps"),
                    _row("d", 20, "incumbentes"), _row("e", 10, "incumbentes")]

    rows, excl = M.build_ranking(base(), sort="total", limit=2, pinned=[], excluded=["a"], groups=None)
    assert [(r["uuid"], r["rank"]) for r in rows] == [("b", 2), ("c", 3)]
    assert excl == [{"uuid": "a", "name": "a", "rank": 1}]

    _, excl = M.build_ranking(base(), sort="total", limit=2, pinned=[], excluded=["e"], groups=None)
    assert excl == []      # "e" (5º) não estaria no Top 2: a exclusão não muda o corte nem o título

    rows, _ = M.build_ranking(base(), sort="total", limit=2, pinned=["e"], excluded=[], groups=None)
    assert [(r["uuid"], r["rank"], r["below_cut"]) for r in rows] == [("a", 1, False), ("b", 2, False), ("e", 5, True)]

    rows, _ = M.build_ranking(base(), sort="total", limit=15, pinned=["d"], excluded=[], groups=["itps"])
    assert [r["uuid"] for r in rows] == ["a", "c", "d"]          # fixada passa pelo filtro de grupos


# ── /meta e páginas (T015) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_returns_v2_palette_institutions_and_dates(client):
    r = await client.get("/api/v2/meta")
    assert r.status_code == 200
    d = r.json()
    assert d["data_through"] == "2026-08-28"
    assert d["updated_at"] == "2026-09-23"
    assert [g["slug"] for g in d["groups"]] == ["neo_banks", "itps", "incumbentes", "outros"]
    from services.constants import GROUP_COLORS_V2
    assert {g["slug"]: g["color"] for g in d["groups"]} == GROUP_COLORS_V2
    brad = next(i for i in d["institutions"] if i["uuid"] == "rec-brad")
    assert brad["short"] == "Bradesco" and brad["group"] == "incumbentes"


@pytest.mark.asyncio
async def test_meta_works_without_status_table(client, use_db, db_no_status):
    use_db(db_no_status)
    r = await client.get("/api/v2/meta")
    assert r.status_code == 200
    assert r.json()["data_through"] == "2026-08-28"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v2", "/v2/evolucao", "/v2/mudancas", "/v2/instituicao", "/"])
async def test_pages_v2_and_legacy_are_served(client, path):
    r = await client.get(path)
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    if path == "/":
        assert 'href="/v2"' in r.text


# ── /ranking (T017) ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ranking_unique_pf_contract(client):
    r = await client.get("/api/v2/ranking", params={"metric": "unique_pf", "limit": 3, "pinned": "rec-brad"})
    assert r.status_code == 200
    d = r.json()
    assert d["week"] == "2026-08-28"
    assert [(x["uuid"], x["rank"], x["below_cut"]) for x in d["rows"]] == [
        ("rec-nu", 1, False), ("rec-belvo", 2, False), ("rec-sant", 3, False), ("rec-brad", 5, True)]
    nu = d["rows"][0]
    assert nu["name"] == "Nubank" and nu["group"] == "neo_banks"
    assert nu["value"] == 5_000_000 + 30_000 * 103
    assert nu["share"] == pytest.approx(nu["value"] / d["ecosystem"]["total"])
    assert nu["pace"]["per_day"] == pytest.approx(30_000 * 4 / 28)
    assert nu["pace"]["trend"] == "flat"
    assert nu["growth"]["kind"] == "pct"
    assert d["ecosystem"]["receptors"] == 6
    assert sum(g["share"] for g in d["ecosystem"]["by_group"]) == pytest.approx(1)


@pytest.mark.asyncio
async def test_ranking_exclusion_debut_and_filters_label(client):
    r = await client.get("/api/v2/ranking", params={"metric": "unique_pf", "limit": 3, "excluded": "rec-belvo,desconhecido"})
    d = r.json()
    assert [(x["uuid"], x["rank"]) for x in d["rows"]] == [("rec-nu", 1), ("rec-sant", 3), ("rec-shop", 4)]
    assert d["excluded"] == [{"uuid": "rec-belvo", "name": "Belvo", "rank": 2}]
    assert d["filters_label"] == "sem Belvo"
    shop = d["rows"][2]
    assert shop["growth"]["kind"] == "debut" and shop["growth"]["debut_month"] == F.WEEKS[F.SHOPEE_DEBUT][:7]


@pytest.mark.asyncio
async def test_ranking_group_filter_keeps_share_on_whole_ecosystem(client):
    d = (await client.get("/api/v2/ranking", params={"metric": "unique_pf", "groups": "itps"})).json()
    assert [x["uuid"] for x in d["rows"]] == ["rec-belvo", "rec-klavi"]
    assert d["filters_label"] == "só ITPs"
    belvo = d["rows"][0]
    assert belvo["share"] == pytest.approx(belvo["value"] / d["ecosystem"]["total"])   # total = ecossistema inteiro

    d = (await client.get("/api/v2/ranking", params={"metric": "unique_pf", "groups": "itps", "pinned": "rec-brad"})).json()
    # a fixada passa pelo filtro e entra na ordem do critério (2,03 mi > Klavi 2,00 mi)
    assert [x["uuid"] for x in d["rows"]] == ["rec-belvo", "rec-brad", "rec-klavi"]


@pytest.mark.asyncio
async def test_ranking_multiplier_for_tiny_base(client):
    d = (await client.get("/api/v2/ranking", params={"metric": "unique_pj", "start": F.WEEKS[0], "limit": 6})).json()
    klavi = next(x for x in d["rows"] if x["uuid"] == "rec-klavi")
    assert klavi["growth"]["kind"] == "multiplier"
    assert klavi["growth"]["value"] == pytest.approx(F.cnpj("rec-klavi", 103) / F.cnpj("rec-klavi", 0))


@pytest.mark.asyncio
async def test_ranking_api_errors_and_per_consent(client):
    d = (await client.get("/api/v2/ranking", params={"metric": "api", "status": "500"})).json()
    nu = next(x for x in d["rows"] if x["uuid"] == "rec-nu")
    assert nu["error_rate"] == pytest.approx(1 / 21)
    assert d["ecosystem"]["error_rate"] is not None

    d = (await client.get("/api/v2/ranking", params={"metric": "api", "scale": "per_consent"})).json()
    nu = next(x for x in d["rows"] if x["uuid"] == "rec-nu")
    last4 = range(F.N_WEEKS - 4, F.N_WEEKS)
    calls30 = sum(F.calls_ok("rec-nu", i) for i in last4) / 4 * 30 / 7
    uniq = sum(F.cpf("rec-nu", i) + F.cnpj("rec-nu", i) for i in last4) / 4
    assert nu["per_consent_month"] == pytest.approx(calls30 / uniq)   # mesma regra da aba 4
    per = [x["per_consent_month"] for x in d["rows"]]
    assert per == sorted(per, reverse=True)
    assert all(x["share"] is None for x in d["rows"])
    assert d["rows"][0]["uuid"] == "rec-klavi"
    assert d["ecosystem"]["top3_share"] is not None


@pytest.mark.asyncio
async def test_ranking_api_fallback_and_unavailable_without_status_table(client, use_db, db_no_status):
    use_db(db_no_status)
    ok = (await client.get("/api/v2/ranking", params={"metric": "api"})).json()
    assert ok["rows"] and ok["unavailable"] == []
    err = (await client.get("/api/v2/ranking", params={"metric": "api", "status": "500"})).json()
    assert err["rows"] == [] and err["unavailable"] == ["errors"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [
    {"metric": "xyz"},
    {"limit": 0},
    {"limit": 51},
    {"sort": "abc"},
    {"metric": "unique_pf", "status": "500"},
    {"metric": "active", "scale": "per_consent"},
    {"start": "2026-13-01"},
    {"start": "2026-09-30"},
])
async def test_ranking_invalid_params_are_422_with_readable_message(client, params):
    r = await client.get("/api/v2/ranking", params=params)
    assert r.status_code == 422
    assert r.json()["detail"]
