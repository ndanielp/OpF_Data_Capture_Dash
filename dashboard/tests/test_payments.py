"""
test_payments.py — Tema Pagamentos (feature 018): GET /api/v2/payments/* e páginas /v2/pagamentos*.

Constitution II: HTTP-level tests against the real FastAPI app with a real SQLite file
(tests/pay_fixtures.py); caminho feliz, erros e tabela ausente em cada rota.
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from tests import pay_fixtures as F  # noqa: E402

P30 = 30 / 28
MONTH = 10_000 * 30 / 7          # 10 mil por semana, num mês de qualquer tamanho


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


async def _client_for(path: Path, mp):
    import config
    mp.setattr(config, "DB_PATH", path)
    import importlib
    import server
    importlib.reload(server)
    return AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")


@pytest_asyncio.fixture(scope="module")
async def client(tmp_path_factory, monkeypatch_module):
    c = await _client_for(F.build_db(tmp_path_factory.mktemp("pay") / "pay.db"), monkeypatch_module)
    async with c:
        yield c


async def _get(client, path, status=200, **params):
    r = await client.get("/api/v2/payments" + path, params=params)
    assert r.status_code == status, r.text
    return r.json()


# ── /meta ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_catalog_roles_and_colors(client):
    d = await _get(client, "/meta")
    assert d["data_through"] == "2026-10-30"
    assert d["months"] == ["2026-08", "2026-09", "2026-10"]
    assert [a["slug"] for a in d["apis"]] == ["payments", "automatic-payments"]
    assert d["apis"][0]["color"].startswith("#") and d["heat"]["fail"].startswith("#")
    by = {i["uuid"]: i for i in d["institutions"]}
    assert by["ini-g"]["short"] == "Google Pay" and by["ini-g"]["roles"] == ["ini"]
    assert by["ini-n"]["roles"] == ["ini", "det"] and by["ini-n"]["in_data"] is True
    assert by["det-s"]["roles"] == ["det"] and by["det-s"]["in_data"] is False


# ── /ranking ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ranking_initiators_values_failure_and_growth(client):
    d = await _get(client, "/ranking")
    eco = d["ecosystem"]
    assert eco["total"] == pytest.approx(202_000 * P30)
    assert eco["initiators"] == 3 and eco["holders"] == 4
    assert eco["payments"]["fail"] == pytest.approx(0.2)
    assert eco["automatic-payments"]["fail"] == pytest.approx(6_000 / 128_000)
    assert [r["name"] for r in d["rows"]] == ["Iniciador", "Google Pay", "Nubank"]
    top = d["rows"][0]
    assert top["value"] == pytest.approx(110_000 * P30)
    assert top["share"] == pytest.approx(110_000 / 202_000)
    assert top["growth"] == pytest.approx(0.10)
    assert top["fail"]["payments"] is None


@pytest.mark.asyncio
async def test_ranking_holders_filtered_by_api(client):
    d = await _get(client, "/ranking", role="det", api="payments")
    assert [r["uuid"] for r in d["rows"]] == ["det-s"]
    assert d["rows"][0]["share"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_ranking_pinned_outside_top_and_excluded(client):
    d = await _get(client, "/ranking", limit=1, pinned="ini-n", excluded="ini-g")
    assert [(r["uuid"], r["cut"]) for r in d["rows"]] == [("ini-a", False), ("ini-n", True)]
    assert d["excluded"] == [{"uuid": "ini-g", "name": "Google Pay"}]


@pytest.mark.asyncio
async def test_ranking_rejects_bad_params(client):
    await _get(client, "/ranking", status=422, role="x")
    await _get(client, "/ranking", status=422, api="pix")


# ── /flows ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flows_monthly_normalization_and_others(client):
    d = await _get(client, "/flows", size=2)
    assert [r["name"] for r in d["rows"]] == ["Iniciador", "Google Pay", "Outras iniciadoras"]
    cols = [c["uuid"] for c in d["cols"]]
    assert cols[-1] is None and len(cols) == 3
    j = cols.index("det-i") if "det-i" in cols else 2
    auto = d["data"]["automatic-payments"]
    # Agosto (1 semana), setembro (4) e outubro (5) com a mesma semana dão o mesmo mês.
    assert [auto[m]["ok"][0][j] for m in d["months"]] == [pytest.approx(MONTH, abs=0.1)] * 3
    assert auto["2026-10"]["fail"][0][j] == pytest.approx(MONTH / 10, abs=0.1)
    await _get(client, "/flows", status=422, size=1)


# ── /enrollment ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrollment_ecosystem_and_holder(client):
    d = await _get(client, "/enrollment")
    assert [s["endpoint"] for s in d["steps"]] == [133, 139, 136, 137]
    assert d["steps"][0]["value"] == pytest.approx(4_000 * P30)
    assert d["conversion"] == pytest.approx(0.48) and d["authorization"] == pytest.approx(500 / 990)
    assert d["ended"] == pytest.approx(80 * P30)
    assert [m["conversion"] for m in d["monthly"]] == [pytest.approx(0.48)] * 3
    other = await _get(client, "/enrollment", transmitter="det-i")
    assert other["steps"][0]["value"] == 0 and other["conversion"] is None
    await _get(client, "/enrollment", status=422, receptor="ini-g", transmitter="ini-n")


# ── /changes ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_changes_confirmed_alert_and_watching(client):
    d = await _get(client, "/changes")
    assert d["week"] == "2026-10-30" and d["floor"] == {"transactions": 30_000, "enrollments": 1_000}
    alerts = {(a["uuid"], a["role"], a["kind"], a["api"]) for a in d["alerts"]}
    assert ("det-s", "det", "fail", "payments") in alerts
    sant = next(a for a in d["alerts"] if a["uuid"] == "det-s")
    assert sant["before"] == pytest.approx(0.0) and sant["after"] == pytest.approx(0.2) and sant["direction"] == "up"
    watching = {(a["uuid"], a["role"], a["kind"]) for a in d["watching"]}
    assert ("det-b", "det", "volume") in watching
    assert ("det-b", "det", "volume") not in {(a["uuid"], a["role"], a["kind"]) for a in d["alerts"]}
    # Abaixo de +20% não vira mudança (Iniciador: +10%).
    assert not any(a["uuid"] == "ini-a" and a["kind"] == "volume" for a in d["alerts"] + d["watching"])


# ── /institution ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_institution_default_role_counterparts_rank_and_enrollment(client):
    d = await _get(client, "/institution/ini-n")
    assert d["role"] == "det" and d["roles"] == ["ini", "det"]
    assert d["institution"]["short"] == "Nubank" and d["institution"]["in_data"] is True
    assert d["counterparts"] == [{"uuid": "ini-a", "name": "Iniciador"}]
    assert d["data"]["automatic-payments"]["2026-10"]["ok"] == [pytest.approx(MONTH / 2, abs=0.1)]
    assert d["ecosystem"]["payments"]["2026-10"]["ok"] == pytest.approx(2 * MONTH, abs=0.1)
    assert d["rank"] == {"position": 4, "of": 4}
    assert d["enrollment"]["conversion"] == pytest.approx(0.48)
    assert d["enrollment_ecosystem"]["conversion"] == pytest.approx(0.48)


@pytest.mark.asyncio
async def test_institution_initiator_role_and_polls(client):
    d = await _get(client, "/institution/ini-n", role="ini")
    assert d["role"] == "ini" and [c["name"] for c in d["counterparts"]] == ["Itaú"]
    assert d["enrollment"] is None
    s = await _get(client, "/institution/det-s", role="ini")     # sem dados como iniciadora
    assert s["role"] == "det" and s["polls"]["payments"] == pytest.approx(2.0)
    assert s["polls"]["automatic-payments"] is None


@pytest.mark.asyncio
async def test_institution_errors(client):
    await _get(client, "/institution/nao-existe", status=404)
    await _get(client, "/institution/ini-n", status=422, role="x")


# ── Tabela ausente e páginas ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_every_route_is_unavailable_without_table(tmp_path, monkeypatch):
    c = await _client_for(F.build_db(tmp_path / "old.db", with_payments=False), monkeypatch)
    async with c:
        for path in ("/meta", "/ranking", "/flows", "/enrollment", "/changes", "/institution/ini-n"):
            d = await _get(c, path)
            assert d["unavailable"] == ["payments"], path


@pytest.mark.asyncio
async def test_pages_are_served(client):
    for path in ("/v2/pagamentos", "/v2/pagamentos/matriz", "/v2/pagamentos/evolucao",
                 "/v2/pagamentos/mudancas", "/v2/pagamentos/instituicao"):
        r = await client.get(path)
        assert r.status_code == 200 and "/static/v2/shell.js" in r.text, path


# ── Feature 019: mês específico, listas escolhidas ───────────────────────────

WEEK = 30 / 7   # um mês com 1 semana de 10 mil vira 10 mil × 30/7


@pytest.mark.asyncio
async def test_meta_monthly_volume_per_role(client):
    d = await _get(client, "/meta")
    nu = next(i for i in d["institutions"] if i["uuid"] == "ini-n")
    assert nu["volume"]["det"] == [pytest.approx(5_000 * WEEK, abs=0.1)] * 3
    assert nu["volume"]["ini"][-1] == pytest.approx(3_000 * WEEK, abs=0.1)
    g = next(i for i in d["institutions"] if i["uuid"] == "ini-g")
    assert g["volume"]["det"] == [0, 0, 0]


@pytest.mark.asyncio
async def test_ranking_of_a_month_compares_with_previous_month(client):
    d = await _get(client, "/ranking", month="2026-09")
    assert d["period"] == {"kind": "month", "month": "2026-09", "prev_month": "2026-08"}
    assert d["window"] == {"start": "2026-09-01", "end": "2026-09-30"}
    top = d["rows"][0]
    assert top["uuid"] == "ini-a" and top["value"] == pytest.approx(25_000 * WEEK, abs=0.1)
    assert top["growth"] == pytest.approx(0.0, abs=1e-9)
    first = await _get(client, "/ranking", month="2026-08")
    assert first["rows"][0]["growth"] is None and first["ecosystem"]["ip_share_prev"] is None
    window = await _get(client, "/ranking")
    assert window["period"] == {"kind": "window"}
    await _get(client, "/ranking", status=422, month="2025-01")


@pytest.mark.asyncio
async def test_ranking_limit_all(client):
    d = await _get(client, "/ranking", limit=500)
    assert len(d["rows"]) == 3
    await _get(client, "/ranking", status=422, limit=501)


@pytest.mark.asyncio
async def test_flows_with_chosen_rows_and_cols(client):
    d = await _get(client, "/flows", rows="ini-n", cols="det-s")
    assert [r["name"] for r in d["rows"]] == ["Nubank", "Outras iniciadoras"]
    assert d["rows"][1]["others_count"] == 2 and d["cols"][1]["others_count"] == 3
    oct_ip = d["data"]["payments"]["2026-10"]["ok"]
    assert oct_ip[0][0] == 0 and oct_ip[1][0] == pytest.approx(20_000 * WEEK, abs=0.1)
    many = ",".join(f"x{i}" for i in range(13))
    await _get(client, "/flows", status=422, rows=many)


@pytest.mark.asyncio
async def test_institution_with_chosen_counterparts(client):
    d = await _get(client, "/institution/ini-n", role="det", counterparts="ini-g")
    assert [c["name"] for c in d["counterparts"]] == ["Google Pay", "Outras iniciadoras"]
    assert d["counterparts"][1]["others_count"] == 1
    ok = d["data"]["automatic-payments"]["2026-10"]["ok"]
    assert ok[0] == 0 and ok[1] == pytest.approx(5_000 * WEEK, abs=0.1)
    many = ",".join(f"x{i}" for i in range(13))
    await _get(client, "/institution/ini-n", status=422, counterparts=many)


@pytest.mark.asyncio
async def test_changes_by_month(client):
    d = await _get(client, "/changes")
    assert [m["month"] for m in d["months"]] == ["2026-08", "2026-09", "2026-10"]
    assert d["months"][-1]["alerts"] == len(d["alerts"])
    sep = await _get(client, "/changes", month="2026-09")
    assert sep["month"] == "2026-09" and sep["week"] == "2026-09-25" and sep["watching"] == []
    assert not any(a["uuid"] == "det-s" and a["kind"] == "fail" for a in sep["alerts"])
    await _get(client, "/changes", status=422, month="2025-01")
