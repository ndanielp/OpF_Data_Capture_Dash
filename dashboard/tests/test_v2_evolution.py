"""
test_v2_evolution.py — Dashboard 2.0 (feature 011): GET /api/v2/evolution
(aba "Como evolui?").

Constitution II: HTTP-level tests against the real FastAPI app with a real SQLite
file, mais testes unitários das regras de ponto mensal e ritmo trimestral.
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

LAST = F.N_WEEKS - 1
START = LAST - 52                     # período padrão: 52 semanas


def pf_shares(i: int) -> dict[str, float]:
    vals = {u: (F.cpf(u, i) or 0) for u in F.INSTITUTIONS}
    tot = sum(vals.values())
    return {u: v / tot for u, v in vals.items()}


@pytest.fixture(scope="module")
def db_full(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2e") / "full.db")


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


async def _get(client, **params):
    r = await client.get("/api/v2/evolution", params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_shape_and_default_five_biggest(client):
    d = await _get(client)
    for key in ("points", "headline", "series", "group_share", "group_share_change",
                "share_changes", "quarterly_pace", "ecosystem_quarterly_pace"):
        assert key in d
    assert d["metric"] == "unique_pf" and d["granularity"] == "month" and d["week"] == F.WEEKS[LAST]
    # PF na última semana: Nubank, Belvo, Santander, Shopee, Bradesco (Klavi é a 6ª).
    assert [s["uuid"] for s in d["series"]] == ["rec-nu", "rec-belvo", "rec-sant", "rec-shop", "rec-brad"]
    assert d["points"][0] == F.WEEKS[START][:7] and d["points"][-1] == "2026-08"
    s = d["series"][0]
    assert len(s["values"]) == len(d["points"]) == len(s["shares"])
    assert s["last"] == F.cpf("rec-nu", LAST)
    assert s["growth"]["value"] == pytest.approx(F.cpf("rec-nu", LAST) / F.cpf("rec-nu", START) - 1)


@pytest.mark.asyncio
async def test_weekly_gap_is_null_never_zero(client):
    d = await _get(client, granularity="week", institutions="rec-belvo")
    gap = d["points"].index(F.GAP_WEEK)
    vals = d["series"][0]["values"]
    assert vals[gap] is None and d["series"][0]["shares"][gap] is None
    assert vals[gap - 1] > 0 and vals[gap + 1] > 0


@pytest.mark.asyncio
async def test_monthly_without_data_in_month_is_null(client):
    # Até 07/08/2026 o Belvo não tem semana com dado em agosto: o mês fica vazio, não zero.
    d = await _get(client, institutions="rec-belvo,rec-nu", end=F.GAP_WEEK)
    assert d["points"][-1] == "2026-08"
    belvo, nu = d["series"]
    assert belvo["values"][-1] is None and belvo["values"][-2] > 0
    assert nu["values"][-1] == F.cpf("rec-nu", F.WEEKS.index(F.GAP_WEEK))


def test_monthly_point_is_last_week_with_data():
    from services import v2_metrics as M
    idx = pd.to_datetime(["2026-07-10", "2026-07-17", "2026-07-24", "2026-07-31"])
    wide = pd.DataFrame({"a": [1.0, 2.0, 3.0, None], "b": [5.0, 6.0, 7.0, 8.0]}, index=idx)
    m = M.by_point(wide, idx[0], idx[-1], "month")
    assert m.loc["2026-07", "a"] == 3.0 and m.loc["2026-07", "b"] == 8.0


@pytest.mark.asyncio
async def test_headline_growth_gainer_and_loser_in_pp(client):
    d = await _get(client)
    h = d["headline"]
    tot = lambda i: sum((F.cpf(u, i) or 0) for u in F.INSTITUTIONS)   # noqa: E731
    eg = h["ecosystem_growth"]
    assert eg["kind"] == "pct" and eg["value"] == pytest.approx(tot(LAST) / tot(START) - 1)
    assert eg["from"] == tot(START) and eg["to"] == tot(LAST)

    a, b = pf_shares(START), pf_shares(LAST)
    pp = {u: (b[u] - a[u]) * 100 for u in F.INSTITUTIONS}
    best, worst = max(pp, key=pp.get), min(pp, key=pp.get)
    assert h["top_gainer"]["uuid"] == best == "rec-shop"
    assert h["top_gainer"]["pp"] == pytest.approx(pp[best])
    assert h["top_gainer"]["debut_month"] == F.WEEKS[F.SHOPEE_DEBUT][:7]
    assert h["top_loser"]["uuid"] == worst and h["top_loser"]["pp"] == pytest.approx(pp[worst])
    # Ganhos primeiro (maior → menor), perdas no fim (a maior perda por último).
    changes = [c["pp"] for c in d["share_changes"]]
    assert changes == sorted(changes, reverse=True)
    assert d["share_changes"][-1]["uuid"] == worst


@pytest.mark.asyncio
async def test_group_share_sums_to_one(client):
    d = await _get(client)
    for row in d["group_share"]:
        assert sum(v for k, v in row.items() if k != "point") == pytest.approx(1.0)
    assert {g["group"] for g in d["group_share_change"]} == {"neo_banks", "itps", "incumbentes", "outros"}


@pytest.mark.asyncio
async def test_quarterly_pace_stable_and_debut_excluded(client):
    d = await _get(client)
    rows = {r["uuid"]: r for r in d["quarterly_pace"]}
    assert rows["rec-klavi"]["status"] == "stable"                 # PF constante: 0% e 0%
    assert rows["rec-klavi"]["months"] == ["2026-02", "2026-05", "2026-08"]
    assert rows["rec-nu"]["status"] == "stable"                    # linear: 5,3% → 5,1%
    assert "rec-shop" not in rows                                   # estreou há menos de 6 meses
    assert d["ecosystem_quarterly_pace"]["status"] in ("stable", "accelerating", "decelerating")


def test_quarterly_pace_threshold():
    from services import v2_metrics as M
    s = lambda v6: pd.Series({"2026-02": 100.0, "2026-05": 110.0, "2026-08": v6})   # noqa: E731
    assert M.quarterly_pace(s(110 * 1.13), "2026-08")["status"] == "stable"        # +10% → +13%
    assert M.quarterly_pace(s(110 * 1.135), "2026-08")["status"] == "accelerating"
    assert M.quarterly_pace(s(110 * 1.065), "2026-08")["status"] == "decelerating"
    assert M.quarterly_pace(pd.Series({"2026-05": 1.0, "2026-08": 2.0}), "2026-08") is None


@pytest.mark.asyncio
async def test_groups_filter_limits_lines_but_not_totals(client):
    all_ = await _get(client)
    d = await _get(client, groups="itps")
    assert [s["uuid"] for s in d["series"]] == ["rec-belvo", "rec-klavi"]
    assert d["headline"]["ecosystem_growth"] == all_["headline"]["ecosystem_growth"]
    assert all(c["group"] == "itps" for c in d["share_changes"])
    assert d["filters_label"] == "só ITPs"


@pytest.mark.asyncio
async def test_api_metric_uses_30_days(client):
    d = await _get(client, metric="api", institutions="rec-nu")
    last4 = sum(F.calls_ok("rec-nu", i) for i in range(LAST - 3, LAST + 1)) / 4 * 30 / 7
    assert d["series"][0]["values"][-1] == pytest.approx(last4)


@pytest.mark.asyncio
async def test_transmitter_view(client):
    d = await _get(client, metric="active", by="transmitter")
    assert d["by"] == "transmitter" and [s["uuid"] for s in d["series"]] == ["txm-1"]
    assert d["series"][0]["last"] == sum(int((F.cpf(u, LAST) or 0) * 1.7) for u in F.INSTITUTIONS)


@pytest.mark.asyncio
async def test_validation_errors(client):
    r = await client.get("/api/v2/evolution", params={"institutions": ",".join(f"u{i}" for i in range(9))})
    assert r.status_code == 422 and "8" in r.json()["detail"]
    r = await client.get("/api/v2/evolution", params={"by": "transmitter"})
    assert r.status_code == 422
    r = await client.get("/api/v2/evolution", params={"granularity": "day"})
    assert r.status_code == 422
    r = await client.get("/api/v2/evolution", params={"start": "2026-09-01"})
    assert r.status_code == 422


# ── Período "Desde o começo do ano" (feature 012) ─────────────────────────────
# O período é só do frontend (V2.periodStart manda start=AAAA-01-01); o backend precisa
# tomar a primeira semana a partir daí como base e aceitar períodos de 1 ponto.

@pytest.mark.asyncio
async def test_year_to_date_start_uses_first_week_of_the_year(client):
    first = next(i for i, w in enumerate(F.WEEKS) if w >= "2026-01-01")
    d = await _get(client, start="2026-01-01")
    tot = lambda i: sum((F.cpf(u, i) or 0) for u in F.INSTITUTIONS)   # noqa: E731
    eg = d["headline"]["ecosystem_growth"]
    assert d["period"]["start"] == "2026-01-01" and d["period"]["end"] == F.WEEKS[LAST]
    assert eg["from"] == tot(first) and eg["to"] == tot(LAST)
    assert eg["value"] == pytest.approx(tot(LAST) / tot(first) - 1)
    assert d["points"][0] == "2026-01"


@pytest.mark.asyncio
async def test_year_to_date_with_a_single_week_is_not_an_error(client):
    first = next(i for i, w in enumerate(F.WEEKS) if w >= "2026-01-01")
    d = await _get(client, start="2026-01-01", end=F.WEEKS[first])
    assert d["points"] == ["2026-01"] and d["week"] == F.WEEKS[first]
    assert d["headline"]["ecosystem_growth"]["value"] == pytest.approx(0.0)


# ── Escala "por consentimento/mês" (feature 012) ──────────────────────────────

@pytest.mark.asyncio
async def test_api_per_consent_matches_ranking_and_hides_shares(client):
    d = await _get(client, metric="api", scale="per_consent", granularity="week")
    assert d["scale"] == "per_consent" and d["share_available"] is False
    # As 5 maiores continuam sendo as de maior volume, não as de maior razão.
    assert [s["uuid"] for s in d["series"]] == ["rec-nu", "rec-belvo", "rec-sant", "rec-shop", "rec-brad"]
    assert all(s["shares"] is None for s in d["series"])
    assert d["group_share"] == [] and d["group_share_change"] == [] and d["share_changes"] == []
    assert d["headline"]["top_gainer"] is None and d["headline"]["top_loser"] is None

    # SC-002: mesma conta de "Quem lidera?" (ranking com escala por consentimento).
    rk = (await client.get("/api/v2/ranking", params={"metric": "api", "scale": "per_consent"})).json()
    by = {r["uuid"]: r["per_consent_month"] for r in rk["rows"]}
    for s in d["series"]:
        assert s["values"][-1] == pytest.approx(by[s["uuid"]]) and s["last"] == pytest.approx(by[s["uuid"]])
    eco = d["ecosystem_series"]["values"]
    assert len(eco) == len(d["points"]) and eco[-1] == pytest.approx(rk["ecosystem"]["per_consent_month"])
    assert d["headline"]["ecosystem_growth"]["to"] == pytest.approx(eco[-1])


@pytest.mark.asyncio
async def test_api_per_consent_gap_week_is_null_and_growth_uses_the_ratio(client):
    d = await _get(client, metric="api", scale="per_consent", granularity="week", institutions="rec-belvo")
    s = d["series"][0]
    assert s["values"][d["points"].index(F.GAP_WEEK)] is None and s["values"][-1] > 0
    first = next(i for i, w in enumerate(F.WEEKS) if w >= d["period"]["start"])
    assert s["growth"]["kind"] == "pct" and s["growth"]["value"] == pytest.approx(s["values"][-1] / s["values"][d["points"].index(F.WEEKS[first])] - 1)


@pytest.mark.asyncio
async def test_api_total_scale_is_unchanged(client):
    default = await _get(client, metric="api")
    explicit = await _get(client, metric="api", scale="total")
    assert default["scale"] == "total" and default["share_available"] is True
    assert default["ecosystem_series"] is None
    assert default["series"] == explicit["series"] and default["share_changes"] == explicit["share_changes"]
    assert all(s["shares"] is not None for s in default["series"])


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"metric": "unique_pf", "scale": "per_consent"},
                                    {"metric": "api", "scale": "xyz"}])
async def test_scale_errors_are_422(client, params):
    r = await client.get("/api/v2/evolution", params=params)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)
