"""
build_consents_db.py — Base de consentimentos únicos por receptor (banco SQLite)
=================================================================================
Coleta consentimentos únicos (CPF + CNPJ) de todos os receptores para um período
e persiste os dados em um banco SQLite com upsert — execuções repetidas atualizam
os registros sem duplicar.

Usa múltiplos workers (ProcessPoolExecutor), cada um com seu próprio browser, para
paralelizar a coleta. O processo principal escreve no banco após coletar todos os
resultados (evita "database is locked").

Uso:
  python3 build_consents_db.py --months 3
  python3 build_consents_db.py --start 2025-01-01 --end 2026-03-01
  python3 build_consents_db.py --db data/outro.db --months 6 --workers 3
"""

import argparse
import copy
import json
import random
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

from contextlib import contextmanager

from unique_consents import fetch_orgs
from utils import (
    BASE_URL, CHROMIUM_BIN,
    console, get_proxy, resolve_date_range, parse_record_date,
    render_table, goto_with_retry, create_browser, create_page,
)

DEFAULT_DB   = Path("data/consents.db")
API_URL      = f"{BASE_URL}/api/unique-consents"
PAGE_URL     = f"{BASE_URL}/transactional-data/unique-consents/receivers"

@contextmanager
def _nullctx():
    yield


WORKER_COUNT   = 3
WORKER_STAGGER = 4  # segundos entre o início de cada worker


# ─────────────────────────────────────────────────────────────────────────────
# Fetch por org — reload por org garante estado limpo do React Select
# ─────────────────────────────────────────────────────────────────────────────

def fetch_consents_for_org(page, org_uuid: str, dates: list[str], click_idx: int = 0) -> list[dict]:
    """
    Dispara POST /api/unique-consents via route interception + click no dropdown.
    Usa expect_response para aguardar a resposta (até 8s).
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

    page.route(API_URL, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/unique-consents" in r.url, timeout=8000
        ) as resp_info:
            page.locator("[class*='-control']").first.click()
            page.wait_for_selector("[class*='-option']", state="visible", timeout=8000)
            page.locator("[class*='-option']").nth(click_idx).click()
        data = resp_info.value.json()
        if isinstance(data, list):
            captured.extend(data)
    except Exception:
        pass
    finally:
        page.unroute(API_URL, route_handler)

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
# Live dashboard
# ─────────────────────────────────────────────────────────────────────────────

def _update_state(states: dict, msg: tuple) -> None:
    kind, wid = msg[0], msg[1]
    if kind == "ready":
        states[wid]["status"]    = "working"
        states[wid]["rec_total"] = msg[2]
    elif kind == "start":
        states[wid]["receptor"] = msg[2]
        states[wid]["rec_idx"]  = msg[3]
        states[wid]["receptors"].append(msg[2])
    elif kind == "org_done":
        states[wid]["recs_done"] += 1
        states[wid]["results"].append("✓" if msg[4] > 0 else "·")
    elif kind == "done":
        states[wid]["status"] = "done"
    elif kind == "log":
        console.print(f"[dim]W{msg[1]} receptores: {msg[2]}[/dim]")


def _make_table(states: dict, start_time: float) -> Table:
    n_total = sum(s["rec_total"] for s in states.values())
    n_done  = sum(s["recs_done"] for s in states.values())
    wids    = sorted(states)

    table = Table(box=rbox.SIMPLE_HEAVY, expand=False, show_edge=True,
                  title="Consentimentos Únicos — Workers")
    table.add_column("Worker",     min_width=8,  style="bold")
    table.add_column("Receptor",   min_width=30)
    table.add_column("Prog.",      min_width=8,  justify="right")
    table.add_column("Resultados", min_width=40)

    for wid in wids:
        s = states[wid]
        if s["status"] == "done":
            worker_cell = f"[green]W{wid} ✓[/green]"
            receptor    = "[dim]concluído[/dim]"
            prog        = f"[green]{s['recs_done']}/{s['rec_total']}[/green]"
        elif s["status"] == "working" and s["receptor"]:
            worker_cell = f"W{wid}"
            receptor    = s["receptor"][:30]
            prog        = f"{s['rec_idx']}/{s['rec_total']}"
        else:
            worker_cell = f"[dim]W{wid}[/dim]"
            receptor    = "[dim]iniciando...[/dim]"
            prog        = f"0/{s['rec_total']}"

        results = s["results"][-40:]
        res_text = Text()
        for sym in results:
            res_text.append("✓", style="green bold") if sym == "✓" else res_text.append("·", style="dim")

        table.add_row(worker_cell, receptor, prog, res_text)

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

    # Escalonar início: evita rajada simultânea que aciona rate limit do CloudFront
    time.sleep((worker_id - 1) * WORKER_STAGGER)

    receptor_list = ", ".join(o["label"] for o in chunk)
    queue.put(("log", worker_id, f"W{worker_id} receptores ({len(chunk)}): {receptor_list}"))

    with sync_playwright() as p:
        queue.put(("ready", worker_id, len(chunk)))
        # Um browser por worker; novo contexto por receptor (isolamento sem re-download)
        browser = create_browser(p)

        for i, org in enumerate(chunk, 1):
            page = create_page(browser)
            goto_with_retry(page, PAGE_URL, "[class*='-control']")
            queue.put(("start", worker_id, org["label"], i))

            raw     = fetch_consents_for_org(page, org["value"], dates, click_idx=0)
            records = build_records(raw, org)
            all_records.extend(records)
            nonzero = sum(1 for r in records if r["total"] > 0)
            queue.put(("org_done", worker_id, org["label"], len(records), nonzero))
            # Fecha o contexto (limpa cookies/storage); browser continua vivo
            page.context.close()
            time.sleep(random.uniform(10, 20))

            if len(preview) < 10:
                preview.extend([r for r in records if r["total"] > 0][:2])

        browser.close()

    queue.put(("done", worker_id))
    return all_records, preview


# ─────────────────────────────────────────────────────────────────────────────
# Sessão
# ─────────────────────────────────────────────────────────────────────────────

def run(dates: list[str], db_path: str | Path, workers: int = WORKER_COUNT,
        on_state_update=None) -> int:
    """
    Coleta consentimentos únicos para todos os receptores e persiste em SQLite.
    Retorna total de registros inseridos/atualizados.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    db_path    = Path(db_path)

    # ── Fetch lista de receptores (processo principal) ─────────────────────────
    console.print("[dim]Carregando lista de receptores...[/dim]")
    with sync_playwright() as p:
        browser = create_browser(p)
        page    = create_page(browser)
        goto_with_retry(page, PAGE_URL, "[class*='-control']")
        orgs = fetch_orgs(page)
        browser.close()

    console.print(f"[green]✓[/green] {len(orgs)} receptores carregados")
    console.print(
        f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} "
        f"({len(dates)} semanas · {len(orgs)} receptores · {workers} workers)[/dim]\n"
    )

    if not orgs:
        return 0

    n      = min(workers, len(orgs))
    chunks = [orgs[i::n] for i in range(n)]  # round-robin para balancear carga

    states = {
        i + 1: {
            "status": "init", "receptor": "", "rec_idx": 0,
            "rec_total": len(chunks[i]), "recs_done": 0, "results": [],
            "receptors": [],
        }
        for i in range(n) if chunks[i]
    }
    start_time  = time.time()
    all_records: list[dict] = []
    all_preview: list[dict] = []

    use_live = on_state_update is None

    with mp.Manager() as mgr:
        queue = mgr.Queue()

        live_ctx = Live(
            _make_table(states, start_time),
            refresh_per_second=4,
            console=console,
            transient=False,
        ) if use_live else None

        with (live_ctx if live_ctx else _nullctx()):
            executor = ProcessPoolExecutor(max_workers=n)
            try:
                futures = {
                    executor.submit(_worker_run, i + 1, chunk, dates, fetched_at, queue): i + 1
                    for i, chunk in enumerate(chunks) if chunk
                }
                completed: set[int] = set()

                while len(completed) < len(futures):
                    while not queue.empty():
                        _update_state(states, queue.get_nowait())

                    elapsed = time.time() - start_time
                    if on_state_update:
                        on_state_update(copy.deepcopy(states), elapsed)
                    elif live_ctx:
                        live_ctx.update(_make_table(states, start_time))

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

                # Drain final
                while not queue.empty():
                    _update_state(states, queue.get_nowait())
                elapsed = time.time() - start_time
                if on_state_update:
                    on_state_update(dict(states), elapsed)
                elif live_ctx:
                    live_ctx.update(_make_table(states, start_time))
            except BaseException:
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)

    # Escrita única no processo principal — sem concorrência
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    total_saved = upsert_records(con, all_records, fetched_at)
    con.close()

    if all_preview:
        render_table(
            all_preview[:20],
            title=f"Consentimentos Únicos (preview {min(20, len(all_preview))} registros)",
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
# Main (CLI)
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Persiste consentimentos únicos (CPF/CNPJ) de todos os receptores em SQLite"
    )
    parser.add_argument("--months",  type=int, metavar="N",    help="Últimos N meses (ex: 3)")
    parser.add_argument("--start",   metavar="YYYY-MM-DD",     help="Data de início")
    parser.add_argument("--end",     metavar="YYYY-MM-DD",     help="Data de fim (padrão: hoje)")
    parser.add_argument("--db",      metavar="PATH",           default=str(DEFAULT_DB),
                        help=f"Caminho do banco SQLite (padrão: {DEFAULT_DB})")
    parser.add_argument("--workers", type=int, metavar="N",    default=WORKER_COUNT,
                        help=f"Número de workers paralelos (padrão: {WORKER_COUNT})")
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

    # Garante que as tabelas existem
    con = open_db(db_path)
    con.close()

    total = run(dates, db_path, workers=args.workers)

    con = open_db(db_path)
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
