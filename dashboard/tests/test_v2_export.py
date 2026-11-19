"""
test_v2_export.py — Portal de exportação de dados (feature 015): /api/v2/export/*.

Constituição II: testes HTTP contra o app FastAPI real (httpx + ASGI) com um SQLite real.
Cobre acesso por código, lista fechada de tabelas, conteúdo do CSV e do ZIP, níveis das
chamadas de API, ticket, contagem e limite de exportações simultâneas.
"""

import csv
import io
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from tests import v2_fixtures as F  # noqa: E402

CODE = "EXPORTAR"
BASE = "/api/v2/export"


@pytest.fixture(scope="module")
def db_full(tmp_path_factory) -> Path:
    return F.build_db(tmp_path_factory.mktemp("export") / "export.db")


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


@pytest.fixture(autouse=True)
def _fresh_limiter():
    from services import export as X
    X.limiter.reset()
    yield
    X.limiter.reset()


async def _login(client, code: str = CODE) -> dict:
    r = await client.post(f"{BASE}/session", json={"code": code})
    assert r.status_code == 200, r.text
    return {"X-Export-Token": r.json()["token"]}


def _rows(body: bytes) -> list[list[str]]:
    text = body.decode("utf-8-sig")
    lines = [l for l in text.split("\r\n") if l and not l.startswith("#")]
    return list(csv.reader(lines, delimiter=";"))


async def _download(client, headers: dict, payload: dict):
    t = await client.post(f"{BASE}/ticket", json=payload, headers=headers)
    assert t.status_code == 200, t.text
    return await client.get(t.json()["url"])


# ── Acesso (FR-020…FR-023, FR-028, SC-007) ────────────────────────────────────

@pytest.mark.asyncio
async def test_login_ok_and_token_opens_options(client):
    headers = await _login(client)
    r = await client.get(f"{BASE}/options", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [t["id"] for t in body["tables"]] == ["unique", "active", "api", "pay"]
    assert body["data_through"] == F.END.isoformat()
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_wrong_code_is_401_and_identical_for_any_wrong_code(client):
    a = await client.post(f"{BASE}/session", json={"code": "errado"})
    b = await client.post(f"{BASE}/session", json={"code": CODE[:-1]})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert "Código inválido" in a.json()["detail"]


@pytest.mark.asyncio
async def test_five_wrong_codes_block_for_a_minute(client):
    for _ in range(4):
        assert (await client.post(f"{BASE}/session", json={"code": "x"})).status_code == 401
    r = await client.post(f"{BASE}/session", json={"code": "x"})
    assert r.status_code == 429 and r.headers["retry-after"] == "60" and r.json()["retry_after"] == 60
    # bloqueado mesmo com o código certo
    assert (await client.post(f"{BASE}/session", json={"code": CODE})).status_code == 429


@pytest.mark.asyncio
async def test_routes_require_token(client):
    assert (await client.get(f"{BASE}/options")).status_code == 401
    assert (await client.get(f"{BASE}/count", params={"tables": "unique"})).status_code == 401
    assert (await client.post(f"{BASE}/ticket", json={"tables": ["unique"]})).status_code == 401
    bad = {"X-Export-Token": "abc.def"}
    assert (await client.get(f"{BASE}/options", headers=bad)).status_code == 401


@pytest.mark.asyncio
async def test_expired_and_other_code_tokens_are_refused(client, monkeypatch):
    from services import export as X
    expired, _ = X.make_token("session", {}, -5)
    assert (await client.get(f"{BASE}/options", headers={"X-Export-Token": expired})).status_code == 401
    headers = await _login(client)
    monkeypatch.setattr(X, "EXPORT_CODE", "outro-codigo-123456")
    r = await client.get(f"{BASE}/options", headers=headers)
    assert r.status_code == 401 and "mudou" in r.json()["detail"]


@pytest.mark.asyncio
async def test_code_is_fixed_on_the_server_and_never_sent_to_the_client(client):
    from services import export as X
    assert X.EXPORT_CODE == "EXPORTAR"
    assert (await client.post(f"{BASE}/session", json={"code": "exportar"})).status_code == 401   # exato
    root = Path(__file__).parent.parent / "gui"
    for f in [*root.glob("v2/*.html"), *root.glob("v2/*.js")]:
        assert "EXPORTAR" not in f.read_text(encoding="utf-8"), f
    page = (await client.get("/v2/exportar")).text
    assert "EXPORTAR" not in page
    for r in (await client.get(f"{BASE}/options"), await client.get("/api/v2/meta")):
        assert "EXPORTAR" not in r.text


@pytest.mark.asyncio
async def test_export_is_not_a_menu_tab_but_the_url_works(client):
    shell = (Path(__file__).parent.parent / "gui" / "v2" / "shell.js").read_text(encoding="utf-8")
    assert "/v2/exportar" not in shell
    assert (await client.get("/v2/exportar")).status_code == 200


@pytest.mark.asyncio
async def test_export_page_is_public(client):
    r = await client.get("/v2/exportar")
    assert r.status_code == 200 and "Exportar dados" in r.text


# ── Lista fechada de tabelas (FR-003, SC-003) ─────────────────────────────────

FORBIDDEN = ["fetch_attempts", "run_summary", "endpoint_history", "api_group_weekly", "api_status_weekly",
             "api_endpoint_weekly", "behavior_signals", "behavior_signals_run", "behavior_watch",
             "sqlite_master", "unique_consents", "nao_existe"]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", FORBIDDEN)
async def test_tables_outside_whitelist_are_refused(client, name):
    headers = await _login(client)
    assert (await client.get(f"{BASE}/count", params={"tables": name}, headers=headers)).status_code == 422
    assert (await client.post(f"{BASE}/ticket", json={"tables": [name]}, headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_forged_ticket_with_foreign_table_is_refused(client):
    from services import export as X
    ticket, _ = X.make_token("ticket", {"req": {"tables": ["fetch_attempts"]}}, 60)
    r = await client.get(f"{BASE}/file", params={"ticket": ticket})
    assert r.status_code == 401
    assert (await client.get(f"{BASE}/file", params={"ticket": "lixo"})).status_code == 401


@pytest.mark.asyncio
async def test_no_collection_columns_exported():
    from services import export as X
    keys = {c["key"] for spec in X.EXPORT_TABLES.values() for c in spec["columns"]}
    assert "fetched_at" not in keys
    assert set(X.EXPORT_TABLES) == {"unique", "active", "api", "pay"}


@pytest.mark.asyncio
async def test_invalid_filters_are_422(client):
    headers = await _login(client)
    for params in ({"tables": "unique", "start": "2026-02-30"},
                   {"tables": "unique", "start": "2026-05-01", "end": "2026-04-01"},
                   {"tables": "unique", "receptors": "a;DROP TABLE x"},
                   {"tables": "unique", "receptors": ",".join(f"r{i}" for i in range(201))},
                   {"tables": "api", "status": "404"},
                   {"tables": "api", "level": "tudo"},
                   {"tables": "api", "apis": "Accounts"},
                   {"tables": "unique,unique"}):
        assert (await client.get(f"{BASE}/count", params=params, headers=headers)).status_code == 422, params


# ── Conteúdo do CSV (US1, SC-002) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unique_csv_content_and_filters(client):
    headers = await _login(client)
    start, end = F.WEEKS[-5], F.WEEKS[-1]
    payload = {"tables": ["unique"], "start": start, "end": end, "receptors": ["rec-nu"]}
    await client.get(f"{BASE}/count", params={"tables": "unique", "start": start, "end": end, "receptors": "rec-nu"}, headers=headers)
    r = await _download(client, headers, payload)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == f'attachment; filename="opf-dados-consentimentos-unicos-{F.END.isoformat()}.csv"'
    assert "content-length" not in r.headers and r.headers["cache-control"] == "no-store"
    assert r.content.startswith(b"\xef\xbb\xbf# Open Finance Brasil")
    text = r.content.decode("utf-8-sig")
    assert "dados até 28/08/2026" in text and "Receptores: NUBANK" in text and "Zeros vieram do portal" in text
    rows = _rows(r.content)
    assert rows[0] == ["Semana", "Receptor", "ID do receptor", "Pessoa física", "Pessoa jurídica", "Total"]
    assert [x[0] for x in rows[1:]] == F.WEEKS[-5:]
    assert {x[2] for x in rows[1:]} == {"rec-nu"}
    # SC-002: os totais são os mesmos que o painel lê da base
    for i, x in zip(range(F.N_WEEKS - 5, F.N_WEEKS), rows[1:]):
        assert [int(x[3]), int(x[4]), int(x[5])] == [F.cpf("rec-nu", i), F.cnpj("rec-nu", i), F.cpf("rec-nu", i) + F.cnpj("rec-nu", i)]
    assert r.headers["x-rows-total"] == "5"     # vem da contagem em cache, sem recontar no download


@pytest.mark.asyncio
async def test_no_receptor_means_all_and_missing_week_has_no_row(client):
    headers = await _login(client)
    r = await _download(client, headers, {"tables": ["unique"], "start": F.GAP_WEEK, "end": F.GAP_WEEK})
    rows = _rows(r.content)[1:]
    assert {x[2] for x in rows} == {"rec-nu", "rec-sant", "rec-klavi", "rec-brad", "rec-shop"}   # Belvo sem coleta: sem linha, não zero
    assert all(x[0] == F.GAP_WEEK for x in rows)


@pytest.mark.asyncio
async def test_transmitter_filter_only_where_it_applies(client):
    headers = await _login(client)
    p = {"tables": ["unique"], "transmitters": ["txm-1"], "start": F.WEEKS[-1], "end": F.WEEKS[-1]}
    r = await _download(client, headers, p)
    assert "Transmissores: não se aplica" in r.content.decode("utf-8-sig")
    assert len(_rows(r.content)) - 1 == 6
    c = (await client.get(f"{BASE}/count", params={"tables": "unique", "transmitters": "txm-1"}, headers=headers)).json()
    assert c["tables"][0]["ignored_filters"] == ["transmitters"]
    p = {"tables": ["active"], "transmitters": ["nenhum"], "start": F.WEEKS[-1], "end": F.WEEKS[-1]}
    assert (await client.get(f"{BASE}/count", params={"tables": "active", "transmitters": "nenhum"}, headers=headers)).json()["total_rows"] == 0


# ── Níveis das chamadas de API (FR-009, SC-006) ───────────────────────────────

@pytest.mark.asyncio
async def test_api_level_total_never_mixes_with_endpoints(client):
    headers = await _login(client)
    base = {"tables": ["api"], "start": F.WEEKS[-1], "end": F.WEEKS[-1], "receptors": ["rec-nu"]}
    total = await _download(client, headers, {**base, "level": "api"})
    rows = _rows(total.content)
    hdr = rows[0]
    assert hdr == ["Semana", "Receptor", "ID do receptor", "Transmissor", "ID do transmissor", "API", "Endpoint",
                   "ID do endpoint", "Status", "Chamadas"]
    assert {x[7] for x in rows[1:]} == {"0"} and {x[6] for x in rows[1:]} == {""}
    assert "nível: total por API" in total.content.decode("utf-8-sig")
    ep = await _download(client, headers, {**base, "level": "endpoint"})
    erows = _rows(ep.content)[1:]
    assert erows and all(x[7] != "0" and x[6] for x in erows)
    assert "nível: por endpoint" in ep.content.decode("utf-8-sig")


@pytest.mark.asyncio
async def test_api_filters_status_api_and_zero_rows(client):
    headers = await _login(client)
    base = {"tables": ["api"], "start": F.WEEKS[-1], "end": F.WEEKS[-1], "receptors": ["rec-nu"]}
    only500 = _rows((await _download(client, headers, {**base, "status": "500"})).content)[1:]
    assert only500 and {x[8] for x in only500} == {"500"}
    loans = _rows((await _download(client, headers, {**base, "apis": ["loans"]})).content)[1:]
    assert len(loans) == 1 and loans[0][5] == "loans" and loans[0][9] == "0"       # zero informado entra (FR-017a)
    tx = _rows((await _download(client, headers, {**base, "transmitters": ["txm-1"]})).content)[1:]
    assert tx and {x[4] for x in tx} == {"txm-1"}
    assert _rows((await _download(client, headers, {**base, "transmitters": ["outro"]})).content)[1:] == []


@pytest.mark.asyncio
async def test_payment_table_labels_and_period(client):
    headers = await _login(client)
    r = await _download(client, headers, {"tables": ["pay"], "receptors": ["rec-nu"]})
    rows = _rows(r.content)
    assert rows[0][1:5] == ["Iniciadora", "ID da iniciadora", "Detentora", "ID da detentora"]
    assert min(x[0] for x in rows[1:]) == F.PAY_FIRST and max(x[0] for x in rows[1:]) == F.PAY_LAST
    out = await client.get(f"{BASE}/count", params={"tables": "pay", "start": "2026-06-01"}, headers=headers)
    assert out.json()["total_rows"] == 0


# ── Ticket e download (US1) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ticket_response_and_expiry(client):
    from services import export as X
    headers = await _login(client)
    t = await client.post(f"{BASE}/ticket", json={"tables": ["unique", "active"]}, headers=headers)
    assert t.status_code == 200
    body = t.json()
    assert body["filename"] == f"opf-dados-{F.END.isoformat()}.zip" and body["expires_in"] == 60
    assert body["url"].startswith(f"{BASE}/file?ticket=")
    old, _ = X.make_token("ticket", {"req": {"tables": ["unique"]}}, -1)
    r = await client.get(f"{BASE}/file", params={"ticket": old})
    assert r.status_code == 401 and "expirou" in r.json()["detail"]


@pytest.mark.asyncio
async def test_ticket_cannot_be_tampered_and_dies_with_the_code(client, monkeypatch):
    headers = await _login(client)
    t = (await client.post(f"{BASE}/ticket", json={"tables": ["unique"], "receptors": ["rec-nu"]}, headers=headers)).json()["url"]
    payload, sig = t.split("=", 1)[1].split(".")
    forged = payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB") + "." + sig
    assert (await client.get(f"{BASE}/file", params={"ticket": forged})).status_code == 401
    assert (await client.get(t)).status_code == 200
    from services import export as X
    monkeypatch.setattr(X, "EXPORT_CODE", "outro-codigo-123456")
    assert (await client.get(t)).status_code == 401


@pytest.mark.asyncio
async def test_file_refuses_third_parallel_export(client):
    from services import export as X
    headers = await _login(client)
    t = (await client.post(f"{BASE}/ticket", json={"tables": ["unique"]}, headers=headers)).json()["url"]
    a, b = X.slots.acquire(), X.slots.acquire()
    assert a and b
    try:
        r = await client.get(t)
        assert r.status_code == 429 and "Outra exportação" in r.json()["detail"]
    finally:
        a.release()
        b.release()
    assert (await client.get(t)).status_code == 200      # liberado depois
    c, d = X.slots.acquire(), X.slots.acquire()          # o download devolveu o lugar
    assert c and d
    c.release()
    d.release()


def test_slot_release_is_idempotent_and_never_frees_another_export():
    from services import export as X
    s = X.ExportSlots(2)
    a = s.acquire()
    a.release()
    b, c = s.acquire(), s.acquire()
    a.release()                      # segunda liberação do mesmo lease: sem efeito
    assert s.acquire() is None       # b e c continuam segurando os 2 lugares
    b.release()
    c.release()


@pytest.mark.asyncio
async def test_other_tabs_keep_answering_while_exports_run(client):
    from services import export as X
    a, b = X.slots.acquire(), X.slots.acquire()
    try:
        assert (await client.get("/api/v2/meta")).status_code == 200
    finally:
        a.release()
        b.release()


# ── Contagem e tamanho (US2) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_count_and_size_estimate(client):
    from services import export as X
    headers = await _login(client)
    r = await client.get(f"{BASE}/count", params={"tables": "unique,active", "receptors": "rec-nu",
                                                   "start": F.WEEKS[-4], "end": F.WEEKS[-1]}, headers=headers)
    body = r.json()
    assert body["total_rows"] == 8 and body["large"] is False
    assert [t["id"] for t in body["tables"]] == ["unique", "active"]
    assert body["tables"][0]["bytes_estimate"] == 4 * X.EXPORT_TABLES["unique"]["avg_bytes"]
    assert body["total_bytes_estimate"] == sum(t["bytes_estimate"] for t in body["tables"])
    assert body["tables"][0]["period"] == {"start": F.WEEKS[-4], "end": F.WEEKS[-1]}


@pytest.mark.asyncio
async def test_count_flags_large_exports(client, monkeypatch):
    from services import export as X
    headers = await _login(client)
    monkeypatch.setattr(X, "LARGE_ROWS", 100)
    X._count_cache.clear()
    r = await client.get(f"{BASE}/count", params={"tables": "unique"}, headers=headers)
    assert r.json()["total_rows"] > 100 and r.json()["large"] is True
    X._count_cache.clear()


@pytest.mark.asyncio
async def test_period_outside_the_base_is_clamped_in_count(client):
    headers = await _login(client)
    r = await client.get(f"{BASE}/count", params={"tables": "unique", "start": "1999-01-01", "end": "2099-01-01"}, headers=headers)
    assert r.json()["tables"][0]["period"] == {"start": F.WEEKS[0], "end": F.WEEKS[-1]}


@pytest.mark.asyncio
async def test_count_is_cached_by_request(client):
    from services import export as X
    headers = await _login(client)
    X._count_cache.clear()
    params = {"tables": "unique", "receptors": "rec-nu"}
    await client.get(f"{BASE}/count", params=params, headers=headers)
    assert len(X._count_cache) == 1
    await client.get(f"{BASE}/count", params=params, headers=headers)
    assert len(X._count_cache) == 1


# ── ZIP (US3) ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_zip_with_two_tables_and_readme(client):
    headers = await _login(client)
    r = await _download(client, headers, {"tables": ["unique", "active"], "receptors": ["rec-nu"],
                                          "transmitters": ["txm-1"], "start": F.WEEKS[-3], "end": F.WEEKS[-1]})
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"] == f'attachment; filename="opf-dados-{F.END.isoformat()}.zip"'
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.namelist() == ["LEIAME.txt", "consentimentos-unicos.csv", "consentimentos-ativos.csv"]
    uni = zf.read("consentimentos-unicos.csv")
    assert not uni.decode("utf-8-sig").startswith("#") and b"#" not in uni
    assert len(_rows(uni)) - 1 == 3
    act = _rows(zf.read("consentimentos-ativos.csv"))
    assert act[0] == ["Semana", "Receptor", "ID do receptor", "Transmissor", "ID do transmissor", "Total"]
    assert len(act) - 1 == 3
    readme = zf.read("LEIAME.txt").decode("utf-8")
    assert "Consentimentos únicos" in readme and "Consentimentos ativos" in readme
    assert "Transmissores: não se aplica" in readme       # filtro que só vale para ativos
    assert "Transmissores: ITAÚ UNIBANCO" in readme
    assert "Pessoa física: Consentimentos únicos de pessoas físicas." in readme
    assert zf.testzip() is None


@pytest.mark.asyncio
async def test_pay_receptor_missing_from_unique_consents_is_named(client, db_full):
    from services import export as X
    con = sqlite3.connect(str(db_full))
    con.execute("INSERT INTO payment_api_requests (receptor_uuid, receptor, transmitter_uuid, transmitter, api, endpoint_id, "
                "endpoint, status, date, total) VALUES ('pisp-x','INICIADORA X','txm-1','ITAÚ UNIBANCO','payments',0,'',200,?,1)", (F.PAY_FIRST,))
    con.commit()
    con.close()
    X._catalog_cache.clear()
    req = X.ExportRequest(tables=["pay"], receptors=["pisp-x"])
    assert "INICIADORA X" in "\n".join(X.describe_filters("pay", req))
    X._catalog_cache.clear()


def test_signing_key_is_slow_derivation_of_the_code(monkeypatch):
    from services import export as X
    monkeypatch.setattr(X, "EXPORT_CODE", "um-codigo-qualquer")
    k1 = X._key()
    monkeypatch.setattr(X, "EXPORT_CODE", "um-codigo-qualquer2")
    assert len(k1) == 32 and X._key() != k1
