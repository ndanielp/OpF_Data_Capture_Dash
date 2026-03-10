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
import multiprocessing as mp
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich import box as rbox
from rich.live  import Live
from rich.panel import Panel
from rich.table import Table
from rich.text  import Text

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

WORKER_COUNT = 5

# Selector do container do dropdown "Receptores" (mesmo padrão do api_requests.py)
RECEPTOR_DROPDOWN = "div.css-48dm8r:has-text('Receptores') [class*='control']"
RECEPTOR_OPTIONS  = "div.css-48dm8r:has-text('Receptores') [class*='option']"


# ─────────────────────────────────────────────────────────────────────────────
# Probe — verifica se receptor tem qualquer chamada no período
# ─────────────────────────────────────────────────────────────────────────────

def probe_receptor(page, receptor_uuid: str, dates: list[str]) -> bool:
    """
    Envia POST sem campo 'apis' — o servidor retorna total agregado do receptor.
    Retorna True se há dados, False se vazio.
    Em caso de erro retorna True (não pula, processa normalmente).
    Usa click_idx=0 (página recém carregada).
    """
    body = {
        "axis":      "date",
        "phase":     "transactional-data",
        "receivers": [receptor_uuid],
        "dates":     dates,
        "status":    200,
    }

    def route_handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    page.route(API_ENDPOINT, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/api-requests" in r.url, timeout=8000
        ) as resp_info:
            page.locator(RECEPTOR_DROPDOWN).first.click()
            page.wait_for_selector(RECEPTOR_OPTIONS, state="visible", timeout=8000)
            page.locator(RECEPTOR_OPTIONS).nth(0).click()
        data = resp_info.value.json()
        return isinstance(data, list) and any(d.get("total", 0) > 0 for d in data)
    except Exception:
        return True  # falha segura: não pula o receptor
    finally:
        page.unroute(API_ENDPOINT, route_handler)


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
            lambda r: "/api/api-requests" in r.url, timeout=8000
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
# Live dashboard — estado e renderização
# ─────────────────────────────────────────────────────────────────────────────

def _update_state(states: dict, msg: tuple) -> None:
    kind, wid = msg[0], msg[1]
    if kind == "ready":
        states[wid]["status"]    = "working"
        states[wid]["rec_total"] = msg[2]
    elif kind == "start":
        states[wid]["receptor"] = msg[2]
        states[wid]["rec_idx"]  = msg[3]
        states[wid]["combos"]   = {(a, s): "" for a in APIS for s in STATUSES}
        if msg[3] > 1:
            states[wid]["recs_done"] += 1
    elif kind == "combo":
        _, _, api_id, status, symbol = msg
        states[wid]["combos"][(api_id, status)] = "✓" if symbol == "+" else "·"
    elif kind == "done":
        states[wid]["status"] = "done"


def _make_table(states: dict, start_time: float) -> Table:
    n_total = sum(s["rec_total"] for s in states.values())
    n_done  = sum(s["recs_done"] for s in states.values())
    wids    = sorted(states)

    table = Table(box=rbox.SIMPLE_HEAVY, expand=False, show_edge=True)
    table.add_column("API", min_width=24, style="dim")

    for wid in wids:
        s = states[wid]
        if s["status"] == "done":
            hdr = f"[green]W{wid}: ✓[/green]"
        elif s["status"] == "working" and s["receptor"]:
            hdr = (
                f"W{wid}: {s['receptor']}\n"
                f"[dim][{s['rec_idx']}/{s['rec_total']}][/dim]"
            )
        else:
            hdr = f"[dim]W{wid}: iniciando...[/dim]"
        table.add_column(hdr, min_width=14)

    for api_id in APIS:
        row: list = [api_id]
        for wid in wids:
            s = states[wid]
            if s["status"] == "init" or not s["combos"]:
                row.append("")
                continue
            cell = Text()
            for status in STATUSES:
                sym = s["combos"].get((api_id, status), "")
                if sym == "✓":
                    cell.append(f"✓{status}", style="green bold")
                elif sym == "·":
                    cell.append(f"·{status}", style="dim")
                else:
                    cell.append(f"○{status}", style="dim")
                cell.append("  ")
            row.append(cell)
        table.add_row(*row)

    mins, secs = divmod(int(time.time() - start_time), 60)
    table.caption = (
        f"Tempo: {mins:02d}:{secs:02d}  |  "
        f"Receptores concluídos: {n_done}/{n_total}"
    )
    return table


# ─────────────────────────────────────────────────────────────────────────────
# Worker (1 browser por processo)
# ─────────────────────────────────────────────────────────────────────────────

def _worker_run(worker_id: int, chunk: list[dict], dates: list[str],
                fetched_at: str, queue) -> tuple[list[dict], list[dict]]:
    """
    Roda em processo separado: apenas fetch via browser, sem escrita em disco.
    Envia progresso via queue. Retorna (all_records, preview_records).
    """
    all_records: list[dict] = []
    preview: list[dict] = []

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
        queue.put(("ready", worker_id, len(chunk)))

        for i, receptor in enumerate(chunk, 1):
            # Reload por receptor: garante estado limpo do React Select
            page.goto(PAGE_URL, wait_until="networkidle", timeout=45000)
            page.wait_for_selector(RECEPTOR_DROPDOWN, timeout=15000)

            queue.put(("start", worker_id, receptor["label"], i))

            # Probe: verifica se receptor tem qualquer chamada (sem "apis")
            # Usa click_idx=0 (primeira interação após reload)
            has_data = probe_receptor(page, receptor["value"], dates)

            if not has_data:
                # Receptor sem dados — marca todos os combos como vazio e pula
                for api_id in APIS:
                    for status in STATUSES:
                        queue.put(("combo", worker_id, api_id, status, "·"))
                continue

            # Probe usou click_idx=0; combos começam em call_count=1 → click_idx=1
            call_count = 1
            for api_id in APIS:
                for status in STATUSES:
                    click_idx  = call_count % 2
                    call_count += 1
                    raw     = fetch_combo(page, receptor["value"], api_id, status, dates, click_idx)
                    records = build_records(raw, receptor, api_id, status, fetched_at)
                    all_records.extend(records)
                    nonzero = sum(1 for r in records if r["total"] > 0)
                    queue.put(("combo", worker_id, api_id, status, "+" if nonzero else "·"))
                    if len(preview) < 10:
                        preview.extend([r for r in records if r["total"] > 0][:2])

        browser.close()
    queue.put(("done", worker_id))
    return all_records, preview


# ─────────────────────────────────────────────────────────────────────────────
# Sessão
# ─────────────────────────────────────────────────────────────────────────────

def run(dates: list[str], receptors: list[dict],
        db_path: str | Path,
        workers: int = WORKER_COUNT) -> int:
    """
    receptors: lista de {"label": str, "value": uuid}
    Retorna total de registros inseridos/atualizados.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    n      = min(workers, len(receptors))
    chunks = [receptors[i::n] for i in range(n)]  # round-robin para balancear carga

    states = {
        i + 1: {
            "status": "init", "receptor": "", "rec_idx": 0,
            "rec_total": len(chunks[i]), "recs_done": 0, "combos": {},
        }
        for i in range(n) if chunks[i]
    }
    start_time   = time.time()
    all_records: list[dict] = []
    all_preview: list[dict] = []

    console.print(
        f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} "
        f"({len(dates)} semanas · {len(receptors)} receptores · "
        f"{len(APIS)} APIs × {len(STATUSES)} statuses = "
        f"{len(receptors) * len(APIS) * len(STATUSES)} chamadas · {n} workers)[/dim]\n"
    )

    with mp.Manager() as mgr:
        queue = mgr.Queue()

        with Live(
            _make_table(states, start_time),
            refresh_per_second=4,
            console=console,
            transient=False,
        ) as live:
            with ProcessPoolExecutor(max_workers=n) as executor:
                futures = {
                    executor.submit(_worker_run, i + 1, chunk, dates, fetched_at, queue): i + 1
                    for i, chunk in enumerate(chunks) if chunk
                }
                completed: set[int] = set()

                while len(completed) < len(futures):
                    # Drain queue
                    while not queue.empty():
                        _update_state(states, queue.get_nowait())
                    live.update(_make_table(states, start_time))

                    # Collect finished futures
                    for future, wid in list(futures.items()):
                        if future.done() and wid not in completed:
                            completed.add(wid)
                            try:
                                recs, prev = future.result()
                                all_records.extend(recs)
                                all_preview.extend(prev)
                                states[wid]["recs_done"] = states[wid]["rec_total"]
                            except Exception as e:
                                console.print(f"[red]W{wid}: {e}[/red]")

                    time.sleep(0.15)

                # Final drain
                while not queue.empty():
                    _update_state(states, queue.get_nowait())
                live.update(_make_table(states, start_time))

    # Escrita única no processo principal — sem concorrência
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    total_saved = upsert_records(con, all_records)
    con.close()

    if all_preview:
        render_table(
            all_preview[:20],
            title=f"API Requests (preview {min(20, len(all_preview))} registros não-zero)",
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

    total = run(dates, receptors, db_path)

    row = con.execute("SELECT count(*) FROM api_requests").fetchone()
    con.close()

    console.print(
        f"\n[bold green]✓ {total} registros inseridos/atualizados[/bold green]\n"
        f"  Banco total api_requests: {row[0]} registros\n"
        f"  → {db_path.resolve()}"
    )


if __name__ == "__main__":
    main()
