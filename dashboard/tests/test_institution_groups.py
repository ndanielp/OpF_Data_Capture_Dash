"""
test_institution_groups.py — HTTP-level tests for the institution-groups filter
(feature 009-filtro-grupos-instituicoes).

Constitution II: each new/modified FastAPI endpoint needs at least one
HTTP-level test covering the happy path and one error/empty case.

Uses httpx.AsyncClient against the real FastAPI app with a tmp SQLite DB —
mirrors the fixture pattern in test_active_consents_api.py.
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

# ── Test data ────────────────────────────────────────────────────────────────
DATE_PREV = "2026-05-12"   # semana anterior — necessária para /api/acceleration
DATE      = "2026-05-19"   # cenário principal (consents, api-requests, resources, matrix)
DATE_RANK = "2026-06-16"   # cenário isolado de /ranking (não afeta a matriz, que usa end=DATE)

# 10 instituições classificadas com volume alto + 2 sem classificação com volume baixo.
# A distribuição é deliberada: os dois "outros" ficam FORA do top-10 global por
# consentimentos, que é o universo usado por _top10_with_bradesco. Sem o recorte de
# grupo aplicado também ao df de consentimentos, groups=outros devolve payload vazio.
CONSENTS_BY_RECEPTOR = [
    # (receptor, total) — ordenado por volume desc
    ("Banco Bradesco S.A.",        10000),  # incumbentes
    ("Itaú Unibanco S.A.",          9000),  # incumbentes
    ("Santander Brasil S.A.",       8000),  # incumbentes
    ("Caixa Econômica Federal",     7000),  # incumbentes
    ("Banco do Brasil S.A.",        6000),  # incumbentes
    ("Nubank S.A.",                 5500),  # neo_banks
    ("Banco Inter S.A.",            5000),  # neo_banks
    ("Banco C6 S.A.",               4500),  # neo_banks
    ("Mercado Pago",                4000),  # neo_banks
    ("PicPay Servicos S.A.",        3500),  # neo_banks
    ("Empresa XYZ Ltda",             200),  # outros — fora do top-10
    ("Cooperativa ABC",              100),  # outros — fora do top-10
]

INCUMBENTES = [r for r, _ in CONSENTS_BY_RECEPTOR[:5]]
NEO_BANKS   = [r for r, _ in CONSENTS_BY_RECEPTOR[5:10]]
OUTROS      = [r for r, _ in CONSENTS_BY_RECEPTOR[10:]]

# unique_consents: (receptor, date, total, cpf, cnpj) — duas semanas para acceleration
UNIQUE_ROWS = (
    [(rec, DATE,      tot,      int(tot * 0.9), int(tot * 0.1)) for rec, tot in CONSENTS_BY_RECEPTOR]
    + [(rec, DATE_PREV, int(tot * 0.9), int(tot * 0.8), int(tot * 0.1)) for rec, tot in CONSENTS_BY_RECEPTOR]
)

# api_requests: (receptor, api, endpoint_id, endpoint, status, date, total)
# 'accounts' alimenta /api/api-requests; 'resources' alimenta /api/resources.
API_ROWS = []
for _rec, _tot in CONSENTS_BY_RECEPTOR:
    API_ROWS.append((_rec, "accounts",  1, "Contas",    200, DATE, _tot * 10))
    API_ROWS.append((_rec, "resources", 1, "Resources", 200, DATE, _tot * 2))

# api_group_weekly: alimenta a série de intensidade de /api/acceleration.
# Um incumbente e um neo bank, duas semanas cada.
AGW_ROWS = [
    # (date, receptor_uuid, receptor, grp, req_week, consents_total)
    (DATE_PREV, "rec-bradesco", "Banco Bradesco S.A.", "Conta", 90000, 9000),
    (DATE,      "rec-bradesco", "Banco Bradesco S.A.", "Conta", 100000, 10000),
    (DATE_PREV, "rec-nubank",   "Nubank S.A.",         "Conta", 49500, 4950),
    (DATE,      "rec-nubank",   "Nubank S.A.",         "Conta", 55000, 5500),
]

# active_consents em DATE — cenário da matriz (filtro nos dois eixos):
#   Bradesco (incumbente) x Itaú Unibanco (incumbente) → sobrevive a groups=incumbentes
#   Bradesco (incumbente) x Nubank (neo_bank)           → cai (transmissor fora do grupo)
#   Nubank (neo_bank)     x Itaú Unibanco (incumbente)  → cai (receptor fora do grupo)
ACTIVE_ROWS = [
    # (receptor_uuid, transmitter_uuid, receptor, transmitter, date, total)
    ("rec-bradesco", "txm-itau",   "Banco Bradesco S.A.", "Itaú Unibanco S.A.", DATE, 300),
    ("rec-bradesco", "txm-nubank", "Banco Bradesco S.A.", "Nubank S.A.",        DATE, 150),
    ("rec-nubank",   "txm-itau",   "Nubank S.A.",          "Itaú Unibanco S.A.", DATE,  80),
]

# active_consents em DATE_RANK — cenário do /ranking: os 4 maiores são neo_banks,
# então um LIMIT aplicado antes do filtro de grupo esconde os incumbentes.
ACTIVE_ROWS_RANK = [
    ("rec-nubank",    "txm-itau", "Nubank S.A.",           "Itaú Unibanco S.A.", DATE_RANK, 5000),
    ("rec-inter",     "txm-itau", "Banco Inter S.A.",      "Itaú Unibanco S.A.", DATE_RANK, 4000),
    ("rec-c6",        "txm-itau", "Banco C6 S.A.",         "Itaú Unibanco S.A.", DATE_RANK, 3000),
    ("rec-mpago",     "txm-itau", "Mercado Pago",          "Itaú Unibanco S.A.", DATE_RANK, 2000),
    ("rec-bradesco",  "txm-itau", "Banco Bradesco S.A.",   "Itaú Unibanco S.A.", DATE_RANK,  900),
    ("rec-santander", "txm-itau", "Santander Brasil S.A.", "Itaú Unibanco S.A.", DATE_RANK,  800),
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("db") / "test_institution_groups.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE unique_consents (
            receptor_uuid TEXT NOT NULL DEFAULT '',
            receptor      TEXT NOT NULL DEFAULT '',
            date          TEXT NOT NULL,
            total         INTEGER NOT NULL DEFAULT 0,
            cpf           INTEGER NOT NULL DEFAULT 0,
            cnpj          INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE active_consents (
            receptor_uuid    TEXT NOT NULL,
            transmitter_uuid TEXT NOT NULL,
            receptor         TEXT NOT NULL DEFAULT '',
            transmitter      TEXT NOT NULL DEFAULT '',
            date             TEXT NOT NULL,
            total            INTEGER NOT NULL,
            fetched_at       TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (receptor_uuid, transmitter_uuid, date)
        );
        CREATE TABLE api_requests (
            receptor_uuid TEXT, receptor TEXT, transmitter_uuid TEXT, transmitter TEXT,
            api TEXT, endpoint_id INTEGER, endpoint TEXT, status INTEGER,
            date TEXT, total INTEGER DEFAULT 0
        );
        CREATE TABLE api_group_weekly (
            date TEXT, receptor_uuid TEXT, receptor TEXT, grp TEXT,
            req_week INTEGER DEFAULT 0, consents_total INTEGER DEFAULT 0,
            PRIMARY KEY (date, receptor_uuid, grp)
        );
        CREATE TABLE fetch_attempts (
            run_id TEXT, phase TEXT, target TEXT, started_at TEXT,
            duration_ms INTEGER, status TEXT, records_count INTEGER,
            error_class TEXT, error_msg TEXT
        );
        CREATE TABLE run_summary (run_id TEXT PRIMARY KEY);
    """)
    con.executemany(
        "INSERT INTO unique_consents (receptor, date, total, cpf, cnpj) VALUES (?,?,?,?,?)",
        UNIQUE_ROWS,
    )
    con.executemany(
        "INSERT INTO active_consents "
        "(receptor_uuid, transmitter_uuid, receptor, transmitter, date, total) VALUES (?,?,?,?,?,?)",
        ACTIVE_ROWS + ACTIVE_ROWS_RANK,
    )
    con.executemany(
        "INSERT INTO api_requests "
        "(receptor, api, endpoint_id, endpoint, status, date, total) VALUES (?,?,?,?,?,?,?)",
        API_ROWS,
    )
    con.executemany(
        "INSERT INTO api_group_weekly "
        "(date, receptor_uuid, receptor, grp, req_week, consents_total) VALUES (?,?,?,?,?,?)",
        AGW_ROWS,
    )
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

    async with AsyncClient(
        transport=ASGITransport(app=server.app),
        base_url="http://test",
    ) as c:
        yield c


# ── GET /api/of/institution-groups (T009) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_institution_groups_metadata_shape(client: AsyncClient):
    r = await client.get("/api/of/institution-groups")
    assert r.status_code == 200
    d = r.json()
    assert set(d["groups"].keys()) == {"incumbentes", "neo_banks", "itps", "outros"}
    for slug, meta in d["groups"].items():
        assert "display" in meta and "color" in meta and "count" in meta
    # Fixture: Bradesco + Itaú Unibanco → incumbentes, Nubank → neo_banks, Empresa XYZ → outros
    assert d["groups"]["incumbentes"]["count"] >= 2
    assert d["groups"]["neo_banks"]["count"] >= 1
    assert d["groups"]["outros"]["count"] >= 1
    assert d["institutions"]["Banco Bradesco S.A."] == "incumbentes"
    assert d["institutions"]["Nubank S.A."] == "neo_banks"
    assert d["institutions"]["Empresa XYZ Ltda"] == "outros"


# ── /api/consents?groups=... (US1: T010, US2: T023, US3: T027/T028) ───────────

@pytest.mark.asyncio
async def test_consents_filtered_by_single_group(client: AsyncClient):
    r = await client.get(f"/api/consents?start={DATE}&end={DATE}&groups=incumbentes")
    assert r.status_code == 200
    d = r.json()
    labels_receptors = {ds["label"] for ds in d.get("datasets", [])} if d.get("datasets") else set()
    # Every dataset present must belong to the incumbentes group
    assert "Nubank S.A." not in labels_receptors
    assert "Empresa XYZ Ltda" not in labels_receptors


@pytest.mark.asyncio
async def test_consents_union_of_two_groups(client: AsyncClient):
    r_single_a = await client.get(f"/api/consents?start={DATE}&end={DATE}&groups=incumbentes")
    r_single_b = await client.get(f"/api/consents?start={DATE}&end={DATE}&groups=neo_banks")
    r_union    = await client.get(f"/api/consents?start={DATE}&end={DATE}&groups=incumbentes,neo_banks")
    assert r_single_a.status_code == r_single_b.status_code == r_union.status_code == 200

    labels_a = {ds["label"] for ds in r_single_a.json().get("datasets", [])}
    labels_b = {ds["label"] for ds in r_single_b.json().get("datasets", [])}
    labels_union = {ds["label"] for ds in r_union.json().get("datasets", [])}
    assert labels_union == labels_a | labels_b


@pytest.mark.asyncio
async def test_consents_outros_bucket_includes_unclassified(client: AsyncClient):
    r = await client.get(f"/api/consents?start={DATE}&end={DATE}&groups=outros")
    assert r.status_code == 200
    labels = {ds["label"] for ds in r.json().get("datasets", [])}
    assert "Empresa XYZ Ltda" in labels
    assert "Banco Bradesco S.A." not in labels


@pytest.mark.asyncio
async def test_consents_all_groups_equals_no_filter(client: AsyncClient):
    r_all_groups = await client.get(
        f"/api/consents?start={DATE}&end={DATE}&groups=incumbentes,neo_banks,itps,outros"
    )
    r_no_filter = await client.get(f"/api/consents?start={DATE}&end={DATE}")
    assert r_all_groups.status_code == r_no_filter.status_code == 200
    labels_all_groups = {ds["label"] for ds in r_all_groups.json().get("datasets", [])}
    labels_no_filter  = {ds["label"] for ds in r_no_filter.json().get("datasets", [])}
    assert labels_all_groups == labels_no_filter


# ── /api/active-consents/matrix?groups=... — dois eixos (T011) ────────────────

@pytest.mark.asyncio
async def test_matrix_filters_both_axes_by_group(client: AsyncClient):
    r = await client.get(f"/api/active-consents/matrix?end={DATE}&groups=incumbentes")
    assert r.status_code == 200
    d = r.json()
    # Only the Bradesco x Itaú Unibanco cell (both incumbentes) should survive
    assert d["receptors"] == ["Banco Bradesco S.A."]
    assert d["transmitters"] == ["Itaú Unibanco S.A."]


@pytest.mark.asyncio
async def test_matrix_no_group_filter_returns_all_cells(client: AsyncClient):
    r = await client.get(f"/api/active-consents/matrix?end={DATE}")
    assert r.status_code == 200
    d = r.json()
    assert set(d["receptors"]) == {"Banco Bradesco S.A.", "Nubank S.A."}
    assert set(d["transmitters"]) == {"Itaú Unibanco S.A.", "Nubank S.A."}


# ── /api/api-requests?groups=... ─────────────────────────────────────────────
# Regressão: o top-10 usado para escolher os receptores vinha do universo global
# de consentimentos. Como nenhum "outros" está no top-10, o recorte por grupo
# resultava em interseção vazia e o heatmap vinha sem dados.

@pytest.mark.asyncio
async def test_api_requests_outros_group_not_empty(client: AsyncClient):
    r = await client.get(f"/api/api-requests?start={DATE}&end={DATE}&groups=outros")
    assert r.status_code == 200
    receptors = r.json().get("receptors", [])
    assert set(receptors) == set(OUTROS)


@pytest.mark.asyncio
async def test_api_requests_incumbentes_only(client: AsyncClient):
    r = await client.get(f"/api/api-requests?start={DATE}&end={DATE}&groups=incumbentes")
    assert r.status_code == 200
    receptors = set(r.json().get("receptors", []))
    assert receptors == set(INCUMBENTES)


# ── /api/resources?groups=... — mesma regressão do heatmap ───────────────────

@pytest.mark.asyncio
async def test_resources_outros_group_not_empty(client: AsyncClient):
    r = await client.get(f"/api/resources?start={DATE}&end={DATE}&groups=outros")
    assert r.status_code == 200
    assert set(r.json().get("receptors", [])) == set(OUTROS)


@pytest.mark.asyncio
async def test_resources_incumbentes_only(client: AsyncClient):
    r = await client.get(f"/api/resources?start={DATE}&end={DATE}&groups=incumbentes")
    assert r.status_code == 200
    assert set(r.json().get("receptors", [])) == set(INCUMBENTES)


# ── /api/acceleration?groups=... ─────────────────────────────────────────────
# Regressão: só a série de consentimentos era filtrada; a série de intensidade
# (api_group_weekly) continuava listando todas as instituições.

@pytest.mark.asyncio
async def test_acceleration_filters_both_series(client: AsyncClient):
    r = await client.get(f"/api/acceleration?start={DATE_PREV}&end={DATE}&groups=incumbentes")
    assert r.status_code == 200
    d = r.json()
    consent_recs   = {s["receptor"] for s in d.get("consent_series", [])}
    intensity_recs = {s["receptor"] for s in d.get("intensity_series", [])}
    assert "Nubank S.A." not in consent_recs
    assert "Nubank S.A." not in intensity_recs
    assert "Banco Bradesco S.A." in intensity_recs


# ── /api/active-consents/ranking?groups=... ──────────────────────────────────
# Regressão: o LIMIT do SQL era aplicado antes do filtro de grupo (em Python),
# então o top-N do grupo era truncado pelo top-N global.

@pytest.mark.asyncio
async def test_ranking_group_returns_full_limit(client: AsyncClient):
    r = await client.get(
        f"/api/active-consents/ranking?end={DATE_RANK}&by=receptor&limit=2&groups=incumbentes"
    )
    assert r.status_code == 200
    items = r.json()["items"]
    # Os 4 maiores da semana são neo_banks; sem a correção, o LIMIT 2*2 do SQL
    # consumia todos eles e o filtro de grupo devolvia lista vazia.
    assert [i["name"] for i in items] == ["Banco Bradesco S.A.", "Santander Brasil S.A."]


@pytest.mark.asyncio
async def test_ranking_no_group_filter_unchanged(client: AsyncClient):
    r = await client.get(f"/api/active-consents/ranking?end={DATE_RANK}&by=receptor&limit=2")
    assert r.status_code == 200
    assert [i["name"] for i in r.json()["items"]] == ["Nubank S.A.", "Banco Inter S.A."]
