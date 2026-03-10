"""
update_db.py — Atualização completa do banco Open Finance Brasil
================================================================
Comando único para atualizar consentimentos únicos e chamadas de API
para todos os receptores ativos em um período.

Fluxo:
  1. Atualiza unique_consents (todos os receptores)
  2. Identifica receptores com consentimentos > 0 no período
  3. Atualiza api_requests (por receptor × API × status)

Uso:
  python3 update_db.py --start 2025-12-01 --end 2025-12-31
  python3 update_db.py --months 3
  python3 update_db.py --months 1 --db data/consents.db
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from rich.panel import Panel
from rich.rule import Rule

from build_consents_db import open_db, run as run_consents
from build_api_requests_db import run as run_api_requests
from utils import console, resolve_date_range

DEFAULT_DB = Path("data/consents.db")


def main():
    parser = argparse.ArgumentParser(
        description="Atualiza consentimentos e chamadas de API no banco SQLite"
    )
    parser.add_argument("--months", type=int, metavar="N", help="Últimos N meses (ex: 3)")
    parser.add_argument("--start",  metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end",    metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--db",     metavar="PATH", default=str(DEFAULT_DB),
                        help=f"Caminho do banco SQLite (padrão: {DEFAULT_DB})")
    parser.add_argument("--skip-consents",    action="store_true", help="Pula atualização de consentimentos")
    parser.add_argument("--skip-api-requests", action="store_true", help="Pula atualização de chamadas de API")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Open Finance Brasil — Atualização do Banco[/bold]\n"
        "[dim]Consentimentos únicos + Chamadas de API por receptor[/dim]",
        border_style="blue",
    ))

    dates = resolve_date_range(args.months, args.start, args.end) or \
            resolve_date_range(months=3, start=None, end=None)

    if not dates:
        console.print("[red]Nenhuma sexta-feira encontrada no período informado.[/red]")
        return

    db_path = Path(args.db)
    console.print(f"[dim]Banco : {db_path.resolve()}[/dim]")
    console.print(f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)[/dim]\n")

    con       = open_db(db_path)
    t_start   = perf_counter()
    n_consents = 0
    n_requests = 0

    # ── 1. Consentimentos ────────────────────────────────────────────────────
    if not args.skip_consents:
        console.print(Rule("[bold cyan]Etapa 1/2 — Consentimentos Únicos[/bold cyan]"))
        n_consents = run_consents(dates, con)
        console.print(f"[green]✓[/green] {n_consents} consentimentos inseridos/atualizados\n")

    # ── 2. Receptores ativos no período ──────────────────────────────────────
    start_date = dates[0][:10]
    end_date   = dates[-1][:10]
    rows = con.execute("""
        SELECT DISTINCT receptor, receptor_uuid
        FROM unique_consents
        WHERE total > 0 AND date BETWEEN ? AND ?
        ORDER BY receptor
    """, (start_date, end_date)).fetchall()
    active_receptors = [{"label": r[0], "value": r[1]} for r in rows]

    console.print(
        f"[dim]{len(active_receptors)} receptores com consentimentos > 0 "
        f"em {start_date} → {end_date}[/dim]\n"
    )

    # ── 3. Chamadas de API ───────────────────────────────────────────────────
    if not args.skip_api_requests:
        if not active_receptors:
            console.print("[yellow]Nenhum receptor ativo — etapa de API requests ignorada.[/yellow]")
        else:
            console.print(Rule("[bold cyan]Etapa 2/2 — Chamadas de API[/bold cyan]"))
            n_requests = run_api_requests(dates, active_receptors, con)
            console.print(f"[green]✓[/green] {n_requests} api_requests inseridos/atualizados\n")

    # ── Resumo ───────────────────────────────────────────────────────────────
    elapsed = perf_counter() - t_start
    r_c = con.execute("SELECT count(*), min(date), max(date) FROM unique_consents").fetchone()
    r_a = con.execute("SELECT count(*), min(date), max(date) FROM api_requests").fetchone()
    con.close()

    console.print(Rule("[bold green]Resumo[/bold green]"))
    console.print(
        f"  unique_consents : {r_c[0]:,} registros  ({r_c[1]} → {r_c[2]})\n"
        f"  api_requests    : {r_a[0]:,} registros  ({r_a[1]} → {r_a[2]})\n"
        f"  Banco           : {db_path.resolve()}\n"
        f"  Tempo total     : {elapsed:.0f}s"
    )


if __name__ == "__main__":
    main()
