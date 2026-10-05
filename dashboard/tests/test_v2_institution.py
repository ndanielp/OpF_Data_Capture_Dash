"""
test_v2_institution.py — Dashboard 2.0 (feature 011): GET /api/v2/institution/{uuid}
(aba "Como opera uma instituição?"), com as regras revisadas em 2026-10-05.

Constitution II: HTTP-level tests against the real FastAPI app with a real SQLite
file; caminho feliz, referências de comparação, tabelas ausentes e erros.
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

LAST = F.N_WEEKS - 1
LAST4 = range(LAST - 3, LAST + 1)


def per_consent_30d(uuid: str) -> float:
    """Chamadas das últimas 4 semanas normalizadas para 30 dias ÷ média de únicos (PF + PJ)."""
    calls = sum(F.calls_ok(uuid, i) for i in LAST4) / 4 * 30 / 7
    uniq = sum(F.cpf(uuid, i) + F.cnpj(uuid, i) for i in LAST4) / 4
    return calls / uniq


@pytest.fixture(scope="module")
def db_full(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2i") / "full.db")


@pytest.fixture(scope="module")
def db_old(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2i") / "old.db", with_status_table=False, with_signals=False)


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


async def _get(client, uuid="rec-nu", **params):
    r = await client.get(f"/api/v2/institution/{uuid}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_kpis_ranks_pace_and_per_consent_30d(client):
    d = await _get(client)
    assert d["institution"] == {"uuid": "rec-nu", "name": "Nubank", "group": "neo_banks",
                                "ranks": {"unique_pf": 1, "unique_pj": 1, "active": 1, "api": 1}}
    assert d["compare"]["label"] == "Ecossistema"
    pf = d["kpis"]["unique_pf"]
    assert pf["value"] == F.cpf("rec-nu", LAST)
    assert pf["growth"]["kind"] == "pct" and pf["ref_growth"]["kind"] == "pct"
    assert pf["pace"]["per_day"] == pytest.approx(30_000 * 4 / 28) and pf["pace"]["trend"] == "flat"
    api = d["kpis"]["api"]
    assert api["pace"]["per_day"] is not None
    assert api["per_consent_month"] == pytest.approx(per_consent_30d("rec-nu"))
    assert api["ref_per_consent_month"] is not None


@pytest.mark.asyncio
async def test_compare_group_and_other_institution_change_references(client):
    eco = await _get(client)
    grp = await _get(client, compare="group")
    other = await _get(client, compare="rec-sant")
    assert grp["compare"]["label"] == "Neobancos (grupo)"
    assert other["compare"] == {"kind": "institution", "uuid": "rec-sant", "label": "Santander"}
    # Nubank é o único neobanco da base de teste: grupo = ele mesmo
    assert grp["kpis"]["api"]["ref_per_consent_month"] == pytest.approx(grp["kpis"]["api"]["per_consent_month"])
    assert other["kpis"]["unique_pf"]["ref_growth"] != eco["kpis"]["unique_pf"]["ref_growth"]


@pytest.mark.asyncio
async def test_evolution_has_all_metrics_monthly_with_share_and_reference_rules(client):
    eco = await _get(client)
    ev = eco["evolution"]
    assert set(ev) == {"unique_total", "unique_pf", "unique_pj", "active", "api", "api_per_consent"}
    tot = ev["unique_total"]
    assert tot["points"] == sorted(set(tot["points"])) and len(tot["points"]) >= 12
    assert tot["values"][-1] == F.cpf("rec-nu", LAST) + F.cnpj("rec-nu", LAST)
    assert all(0 < s < 1 for s in tot["shares"])
    # contagens: referência só contra outra instituição; razão: sempre (mesma escala)
    assert ev["unique_total"]["ref"] is None
    assert ev["api_per_consent"]["ref"]["label"] == "Ecossistema"
    assert ev["api_per_consent"]["shares"] == [None] * len(ev["api_per_consent"]["points"])
    assert ev["api_per_consent"]["values"][-1] == pytest.approx(per_consent_30d("rec-nu"))
    other = await _get(client, compare="rec-sant")
    assert other["evolution"]["unique_pf"]["ref"]["label"] == "Santander"


@pytest.mark.asyncio
async def test_api_mix_units_without_resource(client):
    d = await _get(client)
    assert [m["label"] for m in d["api_mix"]] == ["Contas"]          # base de teste só tem Conta
    m = d["api_mix"][0]
    assert m["share"] == pytest.approx(1)
    assert m["calls_30d"] == pytest.approx(sum(F.calls_ok("rec-nu", i) for i in LAST4) / 4 * 30 / 7)
    assert m["per_consent"] == pytest.approx(per_consent_30d("rec-nu"))
    assert m["ref_per_consent"] is not None


@pytest.mark.asyncio
async def test_api_by_group_has_the_three_units(client):
    d = await _get(client)
    assert all(g["api_group"] != "Resource" for g in d["api_by_group"])
    conta = d["api_by_group"][0]["units"]
    assert set(conta) == {"total", "per_consent", "share"}
    assert conta["total"]["to"] == pytest.approx(sum(F.calls_ok("rec-nu", i) for i in LAST4) / 4 * 30 / 7)
    assert conta["total"]["growth"]["kind"] == "pct"
    assert conta["share"]["growth"] == {"kind": "pp", "value": pytest.approx(0), "debut_month": None}


@pytest.mark.asyncio
async def test_transmitters_with_growth_and_others(client):
    d = await _get(client)
    t = d["transmitters"]
    assert [(x["name"], x["group"], x["share"]) for x in t] == [("Itaú", "incumbentes", 1.0)]   # um só transmissor: sem "Outros"
    assert t[0]["growth"]["kind"] == "pct"


@pytest.mark.asyncio
async def test_error_rate_four_weeks_and_all_months(client):
    d = await _get(client)
    er = d["error_rate"]
    assert er["current"] == pytest.approx(1 / 21)                     # erros = 5% dos sucessos
    assert er["ref_current"] is not None
    assert len(er["series"]) >= 12 and er["series"][-1]["value"] == pytest.approx(1 / 21)
    assert er["by_transmitter"][0]["name"] == "Itaú"


@pytest.mark.asyncio
async def test_alerts_grouped_like_tab_3_with_watch(client):
    nu = await _get(client)
    ev = nu["alerts"]["events"]
    assert [(e["month"], e["kind"], len(e["items"])) for e in ev] == [("2026-08", "decrease", 2)]
    sant = await _get(client, uuid="rec-sant")
    assert [e["kind"] for e in sant["alerts"]["events"] if e["month"] == "2026-08"] == ["oscillation"]
    klavi = await _get(client, uuid="rec-klavi")
    assert [w["api_group_label"] for w in klavi["alerts"]["watching"]] == ["Investimentos"]
    brad = await _get(client, uuid="rec-brad")
    assert brad["alerts"] == {"events": [], "watching": [], "last_alert": None}


@pytest.mark.asyncio
async def test_old_base_marks_errors_and_signals_unavailable(client, use_db, db_old):
    use_db(db_old)
    d = await _get(client)
    assert d["error_rate"] is None
    assert set(d["unavailable"]) == {"errors", "signals"}
    assert d["kpis"]["api"]["value"] == F.calls_ok("rec-nu", LAST)   # cai para api_group_weekly


@pytest.mark.asyncio
async def test_unknown_institution_is_404(client):
    r = await client.get("/api/v2/institution/nao-existe")
    assert r.status_code == 404 and r.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"compare": "xyz"}, {"compare": "rec-nu"}, {"start": "2026-02-30"}, {"start": "2026-09-30"}])
async def test_invalid_params_are_422(client, params):
    r = await client.get("/api/v2/institution/rec-nu", params=params)
    assert r.status_code == 422 and r.json()["detail"]
