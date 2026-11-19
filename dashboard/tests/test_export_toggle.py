"""
test_export_toggle.py — o portal de exportação liga e desliga por deploy (OPF_EXPORT_ENABLED).

Desligado: /v2/exportar e /api/v2/export/* respondem 404, o resto do painel não muda.
Ligado (padrão): tudo como antes.
"""

import importlib
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

_DASHBOARD_ROOT = Path(__file__).parent.parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from tests import v2_fixtures as F  # noqa: E402


async def _app(tmp_path, monkeypatch, value):
    import config
    monkeypatch.setattr(config, "DB_PATH", F.build_db(tmp_path / "t.db"))
    if value is None:
        monkeypatch.delenv("OPF_EXPORT_ENABLED", raising=False)
    else:
        monkeypatch.setenv("OPF_EXPORT_ENABLED", value)
    import server
    importlib.reload(server)
    return server


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "1", "true"])
async def test_export_on_by_default_and_when_enabled(tmp_path, monkeypatch, value):
    server = await _app(tmp_path, monkeypatch, value)
    assert server.EXPORT_ENABLED is True
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        assert (await c.get("/v2/exportar")).status_code == 200
        assert (await c.get("/static/v2/exportar.html")).status_code == 200
        assert (await c.post("/api/v2/export/session", json={"code": "x"})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["0", "false", "off", "no"])
async def test_export_off_removes_page_and_api_only(tmp_path, monkeypatch, value):
    server = await _app(tmp_path, monkeypatch, value)
    assert server.EXPORT_ENABLED is False
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        assert (await c.get("/v2/exportar")).status_code == 404
        assert (await c.get("/static/v2/exportar.html")).status_code == 404        # nem pelo estático
        assert (await c.get("/static/v2/shell.js")).status_code == 200
        for r in (await c.post("/api/v2/export/session", json={"code": "EXPORTAR"}),
                  await c.get("/api/v2/export/options"), await c.get("/api/v2/export/file", params={"ticket": "a.b"})):
            assert r.status_code in (404, 405)
        for p in ("/v2", "/v2/evolucao", "/v2/mudancas", "/v2/instituicao", "/api/v2/meta"):
            assert (await c.get(p)).status_code == 200, p
        assert (await c.get("/", follow_redirects=False)).status_code == 307


@pytest.fixture(autouse=True)
def _restore_server(monkeypatch):
    yield
    monkeypatch.undo()
    import server
    importlib.reload(server)
