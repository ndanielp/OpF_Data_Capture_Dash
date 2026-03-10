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
  python3 update_db.py                          # interface interativa
  python3 update_db.py --start 2025-12-01 --end 2025-12-31
  python3 update_db.py --months 3
  python3 update_db.py --months 1 --db data/consents.db
"""

import argparse
from datetime import date as date_type, datetime
from pathlib import Path
from time import perf_counter

from rich.panel  import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule   import Rule

from build_consents_db import open_db, run as run_consents
from build_api_requests_db import run as run_api_requests
from utils import console, resolve_date_range

DEFAULT_DB = Path("data/consents.db")


# ─────────────────────────────────────────────────────────────────────────────
# Interface interativa de startup
# ─────────────────────────────────────────────────────────────────────────────

def _interactive_setup(db_path_default: Path):
    """Prompts interativos para período e etapas. Retorna (dates, db_path, skip_consents, skip_api)."""

    PERIOD_OPTIONS = {
        "1": ("Último mês",      lambda: resolve_date_range(months=1, start=None, end=None)),
        "2": ("Últimos 3 meses", lambda: resolve_date_range(months=3, start=None, end=None)),
        "3": ("Últimos 6 meses", lambda: resolve_date_range(months=6, start=None, end=None)),
        "4": ("Personalizado",   None),
    }

    console.print("\n [bold]Período de atualização:[/bold]")
    for k, (label, _) in PERIOD_OPTIONS.items():
        console.print(f"   [cyan]{k}[/cyan] · {label}")

    choice = Prompt.ask("\n Opção", choices=list(PERIOD_OPTIONS), default="2")

    if choice == "4":
        while True:
            start_raw = Prompt.ask(" Data de início [dim](YYYY-MM-DD)[/dim]")
            try:
                datetime.fromisoformat(start_raw)
                break
            except ValueError:
                console.print(" [red]Formato inválido. Use YYYY-MM-DD[/red]")

        today_str = date_type.today().isoformat()
        while True:
            end_raw = Prompt.ask(" Data de fim [dim](YYYY-MM-DD)[/dim]", default=today_str)
            try:
                datetime.fromisoformat(end_raw)
                break
            except ValueError:
                console.print(" [red]Formato inválido. Use YYYY-MM-DD[/red]")

        dates = resolve_date_range(months=None, start=start_raw, end=end_raw)
    else:
        dates = PERIOD_OPTIONS[choice][1]()

    if not dates:
        console.print("[red]Nenhuma sexta-feira encontrada no período informado.[/red]")
        raise SystemExit(1)

    console.print()
    skip_consents = not Confirm.ask(" Atualizar consentimentos?",  default=True)
    skip_api      = not Confirm.ask(" Atualizar chamadas de API?", default=True)

    db_raw  = Prompt.ask(" Banco SQLite", default=str(db_path_default))
    db_path = Path(db_raw)

    workers = IntPrompt.ask(" Número de workers", default=5)

    # Resumo
    console.print()
    etapas = " + ".join(filter(None, [
        None if skip_consents else "consentimentos",
        None if skip_api      else "API requests",
    ])) or "[red]nenhuma[/red]"
    console.print(Panel(
        f"  Período : [cyan]{dates[0][:10]} → {dates[-1][:10]}[/cyan]  ({len(dates)} semanas)\n"
        f"  Workers : {workers}\n"
        f"  Etapas  : {etapas}\n"
        f"  Banco   : [dim]{db_path}[/dim]",
        title="Configuração",
        border_style="blue",
    ))

    if not Confirm.ask(" Confirmar e iniciar?", default=True):
        raise SystemExit(0)

    console.print()
    return dates, db_path, skip_consents, skip_api, workers


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Atualiza consentimentos e chamadas de API no banco SQLite"
    )
    parser.add_argument("--months", type=int, metavar="N", help="Últimos N meses (ex: 3)")
    parser.add_argument("--start",  metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end",    metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--db",     metavar="PATH", default=str(DEFAULT_DB),
                        help=f"Caminho do banco SQLite (padrão: {DEFAULT_DB})")
    parser.add_argument("--skip-consents",     action="store_true", help="Pula atualização de consentimentos")
    parser.add_argument("--skip-api-requests", action="store_true", help="Pula atualização de chamadas de API")
    parser.add_argument("--workers", type=int, default=5, metavar="N",
                        help="Número de workers paralelos (padrão: 5)")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Open Finance Brasil — Atualização do Banco[/bold]\n"
        "[dim]Consentimentos únicos + Chamadas de API por receptor[/dim]",
        border_style="blue",
    ))

    # Modo interativo quando nenhum arg de período/etapa foi fornecido
    no_period_args = not any([args.months, args.start, args.end])
    no_step_args   = not any([args.skip_consents, args.skip_api_requests])

    if no_period_args and no_step_args:
        dates, db_path, skip_consents, skip_api_requests, workers = _interactive_setup(Path(args.db))
    else:
        dates = resolve_date_range(args.months, args.start, args.end) or \
                resolve_date_range(months=3, start=None, end=None)
        if not dates:
            console.print("[red]Nenhuma sexta-feira encontrada no período informado.[/red]")
            return
        db_path           = Path(args.db)
        skip_consents     = args.skip_consents
        skip_api_requests = args.skip_api_requests
        workers           = args.workers

    console.print(f"[dim]Banco  : {db_path.resolve()}[/dim]")
    console.print(f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)[/dim]\n")

    con       = open_db(db_path)
    t_start   = perf_counter()
    n_consents = 0
    n_requests = 0

    # ── 1. Consentimentos ────────────────────────────────────────────────────
    if not skip_consents:
        console.print(Rule("[bold cyan]Etapa 1/2 — Consentimentos Únicos[/bold cyan]"))
        n_consents = run_consents(dates, db_path, workers)
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
    if not skip_api_requests:
        if not active_receptors:
            console.print("[yellow]Nenhum receptor ativo — etapa de API requests ignorada.[/yellow]")
        else:
            console.print(Rule("[bold cyan]Etapa 2/2 — Chamadas de API[/bold cyan]"))
            n_requests = run_api_requests(dates, active_receptors, db_path, workers=workers)
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
