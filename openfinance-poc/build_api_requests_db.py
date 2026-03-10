"""
build_api_requests_db.py — Base de chamadas de API por receptor (banco SQLite)
===============================================================================
Coleta volume semanal de chamadas de API por receptor × API × status e persiste
em SQLite. Apenas receptores informados (com consentimentos > 0) são consultados.

O endpoint /api/api-requests é protegido por WAF e exige requisições naturais do
browser. Estratégia: route interception + click no dropdown "Receptores" para
disparar cada chamada autenticamente. O route handler substitui o body inteiro
pela combinação (receptor, api, status, dates) desejada.

Uso direto (debug/teste):
  python3 build_api_requests_db.py --start 2025-12-01 --end 2025-12-31
  python3 build_api_requests_db.py --months 1
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich.panel import Panel

from build_consents_db import open_db
from utils import (
    BASE_URL, CHROMIUM_BIN,
    console, get_proxy, resolve_date_range, parse_record_date,
    render_table,
)

PAGE_URL     = f"{BASE_URL}/transactional-data/api-requests/evolution"
API_ENDPOINT = f"{BASE_URL}/api/api-requests"

APIS = [
    "credit-cards-accounts",
    "consents",
    "accounts",
    "exchanges",
    "customers",
    "funds",
    "unarranged-accounts-overdraft",
    "invoice-financings",
    "loans",
    "financings",
    "resources",
    "bank-fixed-incomes",
    "credit-fixed-incomes",
    "variable-incomes",
    "treasure-titles",
]

STATUSES = [200, 500]

# Selector do container do dropdown "Receptores" (mesmo padrão do api_requests.py)
RECEPTOR_DROPDOWN = "div.css-48dm8r:has-text('Receptores') [class*='control']"
RECEPTOR_OPTIONS  = "div.css-48dm8r:has-text('Receptores') [class*='option']"


# ─────────────────────────────────────────────────────────────────────────────
# Fetch por combinação — route interception + click no dropdown
# ─────────────────────────────────────────────────────────────────────────────

def fetch_combo(page, receptor_uuid: str, api_id: str,
                status: int, dates: list[str], click_idx: int) -> list[dict]:
    """
    Dispara POST /api/api-requests para uma combinação (receptor, api, status)
    via route interception. Clica no dropdown Receptores para acionar a requisição
    natural do Next.js (o route handler substitui o body completo).
    """
    captured: list[dict] = []

    body_override = {
        "axis":      "date",
        "phase":     "transactional-data",
        "apis":      [api_id],
        "receivers": [receptor_uuid],
        "dates":     dates,
        "status":    status,
    }

    def route_handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body_override))
        except Exception:
            route.continue_()

    page.route(API_ENDPOINT, route_handler)

    try:
        with page.expect_response(
            lambda r: "/api/api-requests" in r.url, timeout=15000
        ) as resp_info:
            page.locator(RECEPTOR_DROPDOWN).first.click()
            page.wait_for_selector(RECEPTOR_OPTIONS, state="visible", timeout=8000)
            page.locator(RECEPTOR_OPTIONS).nth(click_idx).click()
        data = resp_info.value.json()
        if isinstance(data, list):
            captured.extend(data)
    except Exception:
        pass
    finally:
        page.unroute(API_ENDPOINT, route_handler)

    return captured


# ─────────────────────────────────────────────────────────────────────────────
# Records
# ─────────────────────────────────────────────────────────────────────────────

def build_records(raw: list[dict], receptor: dict,
                  api_id: str, status: int, fetched_at: str) -> list[dict]:
    records = []
    for item in raw:
        raw_date = str(item.get("date") or item.get("_id") or "")
        if not raw_date:
            continue
        records.append({
            "date":          parse_record_date(raw_date),
            "receptor":      receptor["label"],
            "receptor_uuid": receptor["value"],
            "api":           api_id,
            "status":        status,
            "total":         item.get("total", 0),
            "fetched_at":    fetched_at,
        })
    return records


# ─────────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────────

def upsert_records(con: sqlite3.Connection, records: list[dict]) -> int:
    rows = [
        (r["date"], r["receptor"], r["receptor_uuid"],
         r["api"], r["status"], r["total"], r["fetched_at"])
        for r in records
    ]
    con.executemany("""
        INSERT OR REPLACE INTO api_requests
            (date, receptor, receptor_uuid, api, status, total, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    con.commit()
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Sessão
# ─────────────────────────────────────────────────────────────────────────────

def run(dates: list[str], receptors: list[dict], con: sqlite3.Connection) -> int:
    """
    receptors: lista de {"label": str, "value": uuid}
    Retorna total de registros inseridos/atualizados.
    """
    fetched_at  = datetime.now(timezone.utc).isoformat()
    total_saved = 0
    call_count  = 0  # para alternar click_idx (evita re-seleção no React Select)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            proxy=get_proxy(),
            args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
        )
        page = ctx.new_page()

        # Navega uma vez para inicializar sessão e garantir que os dropdowns existem
        console.print(f"[dim]Carregando página...[/dim]")
        page.goto(PAGE_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(RECEPTOR_DROPDOWN, timeout=15000)
        console.print(
            f"[green]✓[/green] Página carregada\n"
            f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} "
            f"({len(dates)} semanas · {len(receptors)} receptores · "
            f"{len(APIS)} APIs × {len(STATUSES)} statuses = "
            f"{len(receptors) * len(APIS) * len(STATUSES)} chamadas)[/dim]\n"
        )

        preview_records: list[dict] = []

        for i, receptor in enumerate(receptors, 1):
            rec_saved   = 0
            rec_nonzero = 0
            console.print(f"  [{i}/{len(receptors)}] {receptor['label']} ", end="")

            for api_id in APIS:
                for status in STATUSES:
                    click_idx  = call_count % 2
                    call_count += 1

                    raw     = fetch_combo(page, receptor["value"], api_id, status, dates, click_idx)
                    records = build_records(raw, receptor, api_id, status, fetched_at)
                    saved   = upsert_records(con, records)
                    rec_saved   += saved
                    nonzero = sum(1 for r in records if r["total"] > 0)
                    rec_nonzero += nonzero

                    if nonzero:
                        console.print(f"[green]+[/green]", end="")
                    else:
                        console.print(f"[dim]·[/dim]", end="")

                    if len(preview_records) < 20:
                        preview_records.extend([r for r in records if r["total"] > 0][:2])

            console.print(f" [dim]→ {rec_saved} registros ({rec_nonzero} não-zero)[/dim]")
            total_saved += rec_saved

        browser.close()

    if preview_records:
        render_table(
            preview_records[:20],
            title=f"API Requests (preview {min(20, len(preview_records))} registros não-zero)",
            columns=[
                ("date",     "Data",     "left",  "cyan"),
                ("receptor", "Receptor", "left",  "white"),
                ("api",      "API",      "left",  "dim"),
                ("status",   "Status",   "right", "yellow"),
                ("total",    "Total",    "right", "green"),
            ],
        )

    return total_saved


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Persiste chamadas de API por receptor x API x status em SQLite"
    )
    parser.add_argument("--months", type=int, metavar="N")
    parser.add_argument("--start",  metavar="YYYY-MM-DD")
    parser.add_argument("--end",    metavar="YYYY-MM-DD")
    parser.add_argument("--db",     metavar="PATH", default="data/consents.db")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]API Requests — Open Finance Brasil[/bold]\n"
        "[dim]Por receptor x API x status · Banco SQLite (upsert)[/dim]",
        border_style="blue",
    ))

    dates   = resolve_date_range(args.months, args.start, args.end) or \
              resolve_date_range(months=3, start=None, end=None)
    db_path = Path(args.db)
    con     = open_db(db_path)

    start_date, end_date = dates[0][:10], dates[-1][:10]
    rows = con.execute("""
        SELECT DISTINCT receptor, receptor_uuid
        FROM unique_consents
        WHERE total > 0 AND date BETWEEN ? AND ?
        ORDER BY receptor
    """, (start_date, end_date)).fetchall()

    if not rows:
        console.print(
            "[yellow]Nenhum receptor com consentimentos encontrado.\n"
            "Execute build_consents_db.py primeiro.[/yellow]"
        )
        con.close()
        return

    receptors = [{"label": r[0], "value": r[1]} for r in rows]
    console.print(f"[dim]{len(receptors)} receptores ativos no período {start_date} → {end_date}[/dim]\n")

    total = run(dates, receptors, con)

    row = con.execute("SELECT count(*) FROM api_requests").fetchone()
    con.close()

    console.print(
        f"\n[bold green]✓ {total} registros inseridos/atualizados[/bold green]\n"
        f"  Banco total api_requests: {row[0]} registros\n"
        f"  → {db_path.resolve()}"
    )


if __name__ == "__main__":
    main()
