"""
test_v1_removal.py — remoção do painel v1 (feature 016).

Os endereços antigos redirecionam para /v2, as rotas de API do v1 deixam de existir,
a página do v2 não tem mais o link "Painel legado" e a classificação de instituições
(que nasceu no v1 e o v2 usa) continua funcionando.
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
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest_asyncio.fixture(scope="module")
async def client(tmp_path_factory, monkeypatch_module):
    import config
    monkeypatch_module.setattr(config, "DB_PATH", F.build_db(tmp_path_factory.mktemp("v1") / "v1.db"))
    import importlib
    import server
    importlib.reload(server)
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/", "/profile", "/active-consents",
                                  "/?receptor=NUBANK&start=2026-01-01", "/profile?institution=x", "/active-consents?x=1"])
async def test_old_pages_redirect_to_v2(client, path):
    r = await client.get(path, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/v2"          # a query string é descartada


@pytest.mark.asyncio
async def test_redirect_ends_on_the_v2_page(client):
    r = await client.get("/", follow_redirects=True)
    assert r.status_code == 200 and "Open Finance" in r.text and str(r.url).endswith("/v2")


REMOVED = ["/api/of/brand-colors", "/api/of/api-groups", "/api/of/institution-groups", "/api/of/institutions",
           "/api/of/ecosystem-stats", "/api/of/receptor/header", "/api/active-consents/summary", "/api/active-consents/matrix",
           "/api/signals", "/api/receptors", "/api/consents", "/api/api-requests", "/api/api-requests-timeseries",
           "/api/resources", "/api/acceleration", "/api/efficiency", "/api/stats",
           "/static/dashboard.html", "/static/receptor_profile.html", "/static/active_consents.html"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", REMOVED)
async def test_v1_routes_are_gone(client, path):
    r = await client.get(path)
    assert r.status_code == 404, path


@pytest.mark.asyncio
async def test_v2_and_export_pages_still_served(client):
    for p in ("/v2", "/v2/evolucao", "/v2/mudancas", "/v2/instituicao", "/v2/exportar"):
        assert (await client.get(p)).status_code == 200, p
    assert (await client.get("/api/v2/meta")).status_code == 200
    assert (await client.get("/static/v2/shell.js")).status_code == 200


def test_v2_shell_has_no_legacy_link():
    root = _DASHBOARD_ROOT / "gui"
    assert not list(root.glob("*.html"))                       # nenhuma página v1
    for f in [*root.glob("v2/*.html"), *root.glob("v2/*.js")]:
        text = f.read_text(encoding="utf-8")
        assert "Painel legado" not in text and 'href="/"' not in text, f


def test_removed_modules_are_gone():
    for rel in ("routers/openfinance.py", "routers/active_consents.py", "routers/signals.py",
                "services/of_analytics.py", "services/cache.py"):
        assert not (_DASHBOARD_ROOT / rel).exists(), rel


@pytest.mark.parametrize("name,group", [
    ("BRADESCO", "incumbentes"), ("ITAÚ UNIBANCO", "incumbentes"), ("NUBANK", "neo_banks"),
    ("Banco Desconhecido XYZ", "outros"), ("", "outros"), (None, "outros"),
])
def test_resolve_institution_group(name, group):
    from services.constants import resolve_institution_group
    assert resolve_institution_group(name) == group
