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
def db_no_endpoints(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("v2i") / "no_endpoints.db", with_endpoint_table=False)


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


# ── Visão por endpoint (feature 012): GET /api/v2/institution/{uuid}/endpoints ─

def calls_30d(rows_fn) -> float:
    """Soma das últimas 4 semanas ÷ 4 × 30/7 de uma série semanal (mesma regra do mix por grupo)."""
    return sum(rows_fn(i) for i in LAST4) / 4 * 30 / 7


def endpoint_week(uuid: str, api: str, eid: int, i: int) -> int:
    return next((t for a, e, _l, t in F.endpoint_rows(uuid, i) if a == api and e == eid), 0)


async def _endpoints(client, uuid="rec-nu", **params):
    r = await client.get(f"/api/v2/institution/{uuid}/endpoints", params=params)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_endpoints_default_api_lists_all_endpoints_and_closes_the_total(client):
    d = await _endpoints(client)
    assert d["week"] == F.WEEKS[LAST] and d["institution"]["uuid"] == "rec-nu" and d["unavailable"] == []
    # Seletor: só APIs com chamadas, sem o grupo Resource, da maior para a menor.
    assert [a["api"] for a in d["apis"]] == ["accounts", "loans"]
    assert d["apis"][0]["group"] == "Conta" and d["apis"][0]["color"] and d["apis"][0]["label"] == "Contas"
    assert d["api"] == "accounts"
    # Todos os endpoints do catálogo, ordenados por volume; o que ninguém usou fica no fim com zero.
    assert [e["endpoint_id"] for e in d["endpoints"]] == [1, 2, 0, 3]
    assert [e["name"] for e in d["endpoints"]] == ["Saldos da conta", "Extrato da conta", "Sem endpoint identificado", "Limites da conta"]
    assert [e["used"] for e in d["endpoints"]] == [True, True, True, False]
    ep1 = d["endpoints"][0]
    assert ep1["calls_30d"] == pytest.approx(calls_30d(lambda i: endpoint_week("rec-nu", "accounts", 1, i)))
    assert d["endpoints"][-1]["calls_30d"] == 0 and d["endpoints"][-1]["share"] == 0
    # SC-003: a soma dos endpoints (com a parcela sem endpoint) fecha com o total da API.
    total = calls_30d(lambda i: F.calls_ok("rec-nu", i))
    assert d["total"]["calls_30d"] == pytest.approx(total)
    assert sum(e["calls_30d"] for e in d["endpoints"]) == pytest.approx(total)
    assert sum(e["share"] for e in d["endpoints"]) == pytest.approx(1.0)
    assert d["total"]["per_consent"] == pytest.approx(per_consent_30d("rec-nu"))
    assert ep1["per_consent"] == pytest.approx(ep1["calls_30d"] / (d["total"]["calls_30d"] / d["total"]["per_consent"]))


@pytest.mark.asyncio
async def test_endpoints_compare_with_another_institution_and_with_the_ecosystem(client):
    d = await _endpoints(client, compare="rec-brad", api="accounts")
    assert d["compare"]["kind"] == "institution" and d["compare"]["label"] == "Bradesco"
    ep1 = next(e for e in d["endpoints"] if e["endpoint_id"] == 1)
    assert ep1["ref_calls_30d"] == pytest.approx(calls_30d(lambda i: endpoint_week("rec-brad", "accounts", 1, i)))
    assert ep1["ref_share"] == pytest.approx(0.6, abs=1e-3)

    eco = await _endpoints(client, compare="ecosystem", api="accounts")
    assert eco["compare"] == {"kind": "ecosystem", "uuid": None, "label": "Ecossistema"}
    ep2 = next(e for e in eco["endpoints"] if e["endpoint_id"] == 2)
    every = sum(endpoint_week(u, "accounts", 2, i) for u in F.INSTITUTIONS for i in LAST4) / 4 * 30 / 7
    assert ep2["ref_calls_30d"] == pytest.approx(every)
    assert (await _endpoints(client, compare="group", api="accounts"))["compare"]["label"].endswith("(grupo)")


@pytest.mark.asyncio
async def test_endpoints_other_api_and_institution_without_it(client):
    d = await _endpoints(client, api="loans")
    assert [e["endpoint_id"] for e in d["endpoints"]] == [10, 11]          # sem parcela sem endpoint nem zero extra
    assert sum(e["calls_30d"] for e in d["endpoints"]) == pytest.approx(d["total"]["calls_30d"])
    # Bradesco não usa empréstimos: a API nem é oferecida e pedi-la é erro.
    brad = await _endpoints(client, uuid="rec-brad")
    assert [a["api"] for a in brad["apis"]] == ["accounts"]
    r = await client.get("/api/v2/institution/rec-brad/endpoints", params={"api": "loans"})
    assert r.status_code == 422 and "api" in r.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("uuid,params,status", [
    ("nao-existe", {}, 404),
    ("rec-nu", {"compare": "nao-existe"}, 422),
    ("rec-nu", {"compare": "rec-nu"}, 422),
    ("rec-nu", {"api": "resources"}, 422),                              # grupo Resource não é oferecido
    ("rec-nu", {"end": "28/08/2026"}, 422),
])
async def test_endpoints_errors(client, uuid, params, status):
    r = await client.get(f"/api/v2/institution/{uuid}/endpoints", params=params)
    assert r.status_code == status and isinstance(r.json()["detail"], str)


@pytest.mark.asyncio
async def test_endpoints_without_the_table_is_marked_unavailable(client, use_db, db_no_endpoints):
    use_db(db_no_endpoints)
    d = await _endpoints(client)
    assert d["unavailable"] == ["endpoints"] and d["apis"] == [] and d["endpoints"] == [] and d["api"] is None
    # A visão por grupo da mesma base continua funcionando.
    assert (await _get(client))["api_mix"]
