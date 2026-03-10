"""
build_consents_db.py — Base de consentimentos únicos por receptor (banco SQLite)
=================================================================================
Coleta consentimentos únicos (CPF + CNPJ) de todos os receptores para um período
e persiste os dados em um banco SQLite com upsert — execuções repetidas atualizam
os registros sem duplicar.

Uso:
  python3 build_consents_db.py --months 3
  python3 build_consents_db.py --start 2025-01-01 --end 2026-03-01
  python3 build_consents_db.py --start 2025-12-01 --end 2025-12-31
  python3 build_consents_db.py --db data/outro.db --months 6
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich.panel import Panel

from unique_consents import fetch_orgs
from utils import (
    BASE_URL, CHROMIUM_BIN,
    console, get_proxy, resolve_date_range, parse_record_date,
    render_table,
)

DEFAULT_DB = Path("data/consents.db")
API_URL    = f"{BASE_URL}/api/unique-consents"
PAGE_URL   = f"{BASE_URL}/transactional-data/unique-consents/receivers"


# ─────────────────────────────────────────────────────────────────────────────
# Fetch por org — usa click no dropdown (igual ao unique_consents.py)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_consents_for_org(page, org_uuid: str, dates: list[str], click_idx: int = 0) -> list[dict]:
    """
    Dispara POST /api/unique-consents via route interception + click no dropdown.
    click_idx alterna entre 0 e 1 para garantir que React Select dispara onChange
    (re-clicar na opção já selecionada não dispara evento).
    """
    captured: list[dict] = []

    def route_handler(route: Route):
        try:
            body = json.loads(route.request.post_data or "{}")
            body["dates"] = dates
            body["orgs"]  = [org_uuid]
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    def capture_response(resp):
        if "/api/unique-consents" in resp.url:
            try:
                data = resp.json()
                if isinstance(data, list):
                    captured.extend(data)
            except Exception:
                pass

    page.route(API_URL, route_handler)
    page.on("response", capture_response)

    try:
        # Abre o dropdown (selector robusto: funciona com ou sem valor selecionado)
        page.locator("[class*='-control']").first.click()
        # Aguarda as opções ficarem visíveis antes de clicar (evita timeout por timing)
        page.wait_for_selector("[class*='-option']", state="visible", timeout=8000)
        page.locator("[class*='-option']").nth(click_idx).click()
        page.wait_for_timeout(5000)
    except Exception:
        console.print("  [yellow]timeout UI[/yellow]", end=" ")
    finally:
        page.unroute(API_URL, route_handler)
        page.remove_listener("response", capture_response)

    return captured


def build_records(raw: list[dict], org: dict) -> list[dict]:
    return [
        {
            "date":          parse_record_date(str(item.get("date") or item.get("_id") or "")),
            "receptor":      org["label"],
            "receptor_uuid": org["value"],
            "cpf":           item.get("cpf", 0),
            "cnpj":          item.get("cnpj", 0),
            "total":         item.get("cpf", 0) + item.get("cnpj", 0),
        }
        for item in raw
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Banco de dados
# ─────────────────────────────────────────────────────────────────────────────

def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS unique_consents (
            date           TEXT NOT NULL,
            receptor       TEXT NOT NULL,
            receptor_uuid  TEXT NOT NULL,
            cpf            INTEGER NOT NULL DEFAULT 0,
            cnpj           INTEGER NOT NULL DEFAULT 0,
            total          INTEGER NOT NULL DEFAULT 0,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS api_requests (
            date           TEXT NOT NULL,
            receptor       TEXT NOT NULL,
            receptor_uuid  TEXT NOT NULL,
            api            TEXT NOT NULL,
            status         INTEGER NOT NULL,
            total          INTEGER NOT NULL DEFAULT 0,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid, api, status)
        )
    """)
    con.commit()
    return con


def upsert_records(con: sqlite3.Connection, records: list[dict], fetched_at: str) -> int:
    rows = [
        (r["date"], r["receptor"], r["receptor_uuid"],
         r["cpf"], r["cnpj"], r["total"], fetched_at)
        for r in records
    ]
    con.executemany("""
        INSERT OR REPLACE INTO unique_consents
            (date, receptor, receptor_uuid, cpf, cnpj, total, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    con.commit()
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Sessão
# ─────────────────────────────────────────────────────────────────────────────

def run(dates: list[str], con: sqlite3.Connection) -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    total_saved = 0

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

        orgs = fetch_orgs(page)
        console.print(f"[green]✓[/green] {len(orgs)} receptores carregados")
        console.print(f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)[/dim]\n")

        if not orgs:
            browser.close()
            return 0

        preview_records: list[dict] = []

        for i, org in enumerate(orgs, 1):
            console.print(f"  [{i}/{len(orgs)}] {org['label']}", end=" ")
            raw = fetch_consents_for_org(page, org["value"], dates, click_idx=i % 2)
            records = build_records(raw, org)
            saved = upsert_records(con, records, fetched_at)
            total_saved += saved
            if len(preview_records) < 20:
                preview_records.extend(records)
            console.print(f"[dim]→ {len(records)} semanas[/dim]")

        browser.close()

    if preview_records:
        render_table(
            preview_records[:20],
            title=f"Consentimentos Únicos (preview {min(20, len(preview_records))} registros)",
            columns=[
                ("date",     "Data",     "left",  "cyan"),
                ("receptor", "Receptor", "left",  "white"),
                ("cpf",      "CPF",      "right", "green"),
                ("cnpj",     "CNPJ",     "right", "blue"),
                ("total",    "Total",    "right", "bold white"),
            ],
        )

    return total_saved


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Persiste consentimentos únicos (CPF/CNPJ) de todos os receptores em SQLite"
    )
    parser.add_argument("--months", type=int, metavar="N", help="Últimos N meses (ex: 3)")
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end",   metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--db",    metavar="PATH", default=str(DEFAULT_DB),
                        help=f"Caminho do banco SQLite (padrão: {DEFAULT_DB})")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Consentimentos Únicos — Open Finance Brasil[/bold]\n"
        "[dim]Todos os receptores · Banco SQLite (upsert)[/dim]",
        border_style="blue",
    ))

    dates = resolve_date_range(args.months, args.start, args.end) or \
            resolve_date_range(months=3, start=None, end=None)

    if not dates:
        console.print("[red]Nenhuma sexta-feira encontrada no período informado.[/red]")
        return

    db_path = Path(args.db)
    console.print(f"[dim]Banco: {db_path.resolve()}[/dim]")
    console.print(f"[dim]Semanas alvo: {[d[:10] for d in dates]}[/dim]\n")

    con = open_db(db_path)
    total = run(dates, con)

    row = con.execute(
        "SELECT count(*), min(date), max(date) FROM unique_consents"
    ).fetchone()
    con.close()

    console.print(
        f"\n[bold green]✓ {total} registros inseridos/atualizados[/bold green]\n"
        f"  Banco total: {row[0]} registros · {row[1]} → {row[2]}\n"
        f"  → {db_path.resolve()}"
    )


if __name__ == "__main__":
    main()
