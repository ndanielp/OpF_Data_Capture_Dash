"""
server.py — FastAPI backend do Dashboard 2.0
============================================
Serve as páginas `/v2*`, a API `/api/v2/*` (inclusive a exportação de dados) e os arquivos
estáticos. As páginas do painel v1 foram removidas (feature 016): `/`, `/profile` e
`/active-consents` apenas redirecionam para `/v2`.
"""

import os
import sqlite3
import threading
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config

# Portal de exportação (feature 015) ligado/desligado por deploy: OPF_EXPORT_ENABLED=0 tira a página
# /v2/exportar e a API /api/v2/export/* (404). Padrão: ligado. O deploy.sh/deploy.ps1 definem a variável.
EXPORT_ENABLED = os.environ.get("OPF_EXPORT_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off", "")

def _db_con() -> sqlite3.Connection:
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute("PRAGMA cache_size = -4096")   # limita page cache do SQLite a 4 MB
    # WAL + mmap + memory temp: read-only dashboard talks to a DB that the
    # collector writes in WAL mode; setting here lets queries stream pages
    # through mmap instead of syscalls, and keeps temp tables off disk.
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA mmap_size = 268435456")
    con.execute("PRAGMA temp_store = MEMORY")
    return con

def _ensure_dashboard_indexes() -> None:
    """Compound covering index the dashboard's consents queries need.

    The collector's scrapers.py ships single-column indexes; without this,
    queries filtered by (date, receptor_uuid) fall back to seek + row fetch.
    Wait up to 3s if the collector holds a write lock rather than crash.
    """
    try:
        con = _db_con()
        try:
            con.execute("PRAGMA busy_timeout = 3000")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_consents_date_rec "
                "ON unique_consents(date, receptor_uuid, total)"
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def _ensure_active_consents_indexes() -> None:
    """Índices compostos para as queries de consentimentos ativos.

    Cobre os padrões: filter-by-date + group-by-receptor e
    filter-by-date + group-by-transmitter usados pelos endpoints
    /api/active-consents/*.
    """
    try:
        con = _db_con()
        try:
            con.execute("PRAGMA busy_timeout = 3000")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_date_receptor "
                "ON active_consents(date, receptor_uuid)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_active_date_transmitter "
                "ON active_consents(date, transmitter_uuid)"
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def _ensure_api_group_weekly():
    """Garante schema de api_group_weekly em DBs antigos. A população é responsabilidade
    do data-loader (scrapers.refresh_api_group_weekly) — aqui só criamos a tabela se ausente."""
    con = sqlite3.connect(str(config.DB_PATH))
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS api_group_weekly (
                date           TEXT    NOT NULL,
                receptor_uuid  TEXT    NOT NULL,
                receptor       TEXT    NOT NULL DEFAULT '',
                grp            TEXT    NOT NULL,
                req_week       INTEGER NOT NULL DEFAULT 0,
                consents_total INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date, receptor_uuid, grp))
        """)
        con.commit()
    finally:
        con.close()



def _warm_v2_cache():
    """Dashboard 2.0: carrega as séries pesadas antes do primeiro acesso."""
    try:
        from services import v2_metrics
        v2_metrics.warm()
    except Exception:
        pass
    if not EXPORT_ENABLED:
        return
    try:   # exportação (feature 015): catálogo e contagem inicial, para a primeira contagem sair rápida
        from services import export as export_service
        export_service.catalog()
        export_service.count_rows(export_service.ExportRequest(tables=["unique"]))
    except Exception:
        pass



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Garante que api_group_weekly exista (DBs antigos) e os índices que o v2 e a exportação usam.
    _ensure_api_group_weekly()
    _ensure_dashboard_indexes()
    _ensure_active_consents_indexes()
    # Pré-aquece o cache em background — o servidor aceita conexões imediatamente.
    threading.Thread(target=_warm_v2_cache, daemon=True).start()
    yield


from routers import v2 as v2_router
from routers import export as export_router

app = FastAPI(title="OPF Batch Dashboard", lifespan=lifespan)
app.include_router(v2_router.router, prefix="/api/v2")
if EXPORT_ENABLED:
    app.include_router(export_router.router, prefix="/api/v2/export")

GUI_DIR = Path(__file__).parent / "gui"

# Dashboard 2.0 (feature 011) — uma página por aba; `/v2/exportar` fica fora do menu (feature 015).
_V2_PAGES = {
    "/v2": "index.html",
    "/v2/evolucao": "evolucao.html",
    "/v2/mudancas": "mudancas.html",
    "/v2/instituicao": "instituicao.html",
}
if EXPORT_ENABLED:
    _V2_PAGES["/v2/exportar"] = "exportar.html"


def _v2_page(filename: str):
    async def page() -> HTMLResponse:
        return HTMLResponse((GUI_DIR / "v2" / filename).read_text(encoding="utf-8"))
    return page


for _route, _file in _V2_PAGES.items():
    app.add_api_route(_route, _v2_page(_file), methods=["GET"], response_class=HTMLResponse,
                      include_in_schema=False)


def _to_v2():
    async def redirect() -> RedirectResponse:
        # 307 (e não 301): o navegador não guarda o destino de forma permanente. A query string é descartada.
        return RedirectResponse("/v2", status_code=307)
    return redirect


# Endereços do painel v1 (removido na feature 016) levam ao Dashboard 2.0.
for _old in ("/", "/profile", "/active-consents"):
    app.add_api_route(_old, _to_v2(), methods=["GET", "HEAD"], include_in_schema=False)


class _RevalidatingStatic(StaticFiles):
    """StaticFiles que manda Cache-Control: no-cache. Sem cabeçalho, o navegador guarda o JS/CSS
    por tempo heurístico e pode juntar um shell.js antigo com uma página nova (TypeError, tela
    quebrada). Com no-cache ele revalida a cada carga pelo ETag e recebe 304 quando nada mudou."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", _RevalidatingStatic(directory=str(GUI_DIR)), name="static")

def run_server(port: int = 8000):
    GUI_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Iniciando Dashboard Servidor em http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
