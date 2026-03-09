"""
unique_consents.py — Consentimentos únicos por receptor
========================================================
Captura dados de consentimentos únicos (CPF + CNPJ) por receptor ou transmissor.

Uso:
  python3 unique_consents.py --list-orgs
  python3 unique_consents.py --receiver "BANCO BMG"
  python3 unique_consents.py --receiver "Itaú" --months 6
  python3 unique_consents.py --receiver "BTG" --start 2025-10-01 --end 2026-01-31
  python3 unique_consents.py -r "BTG" -r "C6" --months 6
  python3 unique_consents.py --all-orgs --months 3
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich.table import Table
from rich.panel import Panel

from utils import (
    BASE_URL, CHROMIUM_BIN, OUTPUT_DIR,
    console, get_proxy, resolve_date_range, parse_record_date, save_json,
)

PAGE_URL = f"{BASE_URL}/transactional-data/unique-consents/receivers"


# ─────────────────────────────────────────────────────────────────────────────
# Browser session
# ─────────────────────────────────────────────────────────────────────────────

def fetch_orgs(page) -> list[dict]:
    """Navega para a página e captura a lista de organizações disponíveis."""
    orgs = []

    def capture_orgs(resp):
        if "/api/organisations" in resp.url:
            try:
                orgs.extend(resp.json())
            except Exception:
                pass

    page.on("response", capture_orgs)
    page.goto(PAGE_URL, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(1000)
    return orgs


def fetch_unique_consents(org_uuids: list[str], dates: list[str], page) -> list[dict]:
    """
    Dispara POST /api/unique-consents com as orgs e datas desejadas.
    Usa route interception para injetar os parâmetros no body antes do envio.
    """
    captured = []

    def route_handler(route: Route):
        try:
            body = json.loads(route.request.post_data or "{}")
            body["dates"] = dates
            body["orgs"] = org_uuids
            route.continue_(post_data=json.dumps(body))
        except Exception as e:
            console.print(f"  [yellow]Route erro: {e}[/yellow]")
            route.continue_()

    def capture_response(resp):
        if "/api/unique-consents" in resp.url:
            try:
                data = resp.json()
                if isinstance(data, list):
                    captured.extend(data)
            except Exception:
                pass

    page.route(f"{BASE_URL}/api/unique-consents", route_handler)
    page.on("response", capture_response)

    # Seleciona a primeira org no dropdown para disparar o fetch
    page.locator(".css-13cymwt-control").click()
    page.wait_for_timeout(400)
    page.locator("[class*='option']").first.click()
    page.wait_for_timeout(5000)

    return captured


def run_session(
    org_names: list[str] | None,
    all_orgs: bool,
    dates: list[str],
    list_orgs: bool,
) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            proxy=get_proxy(),
            args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            ignore_https_errors=True, viewport={"width": 1440, "height": 900}, locale="pt-BR",
        )
        page = ctx.new_page()

        orgs = fetch_orgs(page)
        console.print(f"[green]✓[/green] {len(orgs)} organizações carregadas")

        if list_orgs or not orgs:
            browser.close()
            return {"orgs": orgs, "data": []}

        if all_orgs:
            target_orgs = orgs
        elif org_names:
            target_orgs = []
            for name in org_names:
                matches = [o for o in orgs if name.lower() in o["label"].lower()]
                if not matches:
                    console.print(f"[yellow]⚠ Nenhuma org encontrada para '{name}'[/yellow]")
                else:
                    target_orgs.extend(matches)
            if not target_orgs:
                browser.close()
                return {"orgs": orgs, "data": []}
        else:
            console.print("[yellow]Use --receiver <nome> ou --all-orgs[/yellow]")
            browser.close()
            return {"orgs": orgs, "data": []}

        console.print(
            f"[dim]Buscando {len(target_orgs)} org(s): "
            f"{[o['label'] for o in target_orgs[:5]]}...[/dim]"
        )
        console.print(
            f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} sextas)[/dim]"
        )

        org_uuids = [o["value"] for o in target_orgs]
        raw = fetch_unique_consents(org_uuids, dates, page)
        browser.close()

    org_label = target_orgs[0]["label"] if len(target_orgs) == 1 else f"{len(target_orgs)} orgs"
    records = []
    for item in raw:
        raw_date = str(item.get("date") or item.get("_id") or "")
        records.append({
            "date": parse_record_date(raw_date),
            "cpf": item.get("cpf", 0),
            "cnpj": item.get("cnpj", 0),
            "total": item.get("cpf", 0) + item.get("cnpj", 0),
            "org": org_label,
        })

    return {"orgs": orgs, "data": sorted(records, key=lambda r: r["date"])}


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_consents(records: list[dict], title: str):
    """Renderiza tabela com colunas CPF / CNPJ / Total (e Org quando multi-org)."""
    if not records:
        console.print("[yellow]Nenhum dado capturado.[/yellow]")
        return
    multi_org = len({r["org"] for r in records}) > 1
    table = Table(title=title, show_lines=True)
    table.add_column("Data", style="cyan", no_wrap=True)
    table.add_column("CPF", justify="right", style="green")
    table.add_column("CNPJ", justify="right", style="blue")
    table.add_column("Total", justify="right", style="bold white")
    if multi_org:
        table.add_column("Org", style="dim")
    for r in records:
        row = [r["date"], f"{r['cpf']:,}", f"{r['cnpj']:,}", f"{r['total']:,}"]
        if multi_org:
            row.append(r["org"])
        table.add_row(*row)
    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Captura consentimentos únicos (CPF/CNPJ) do Dashboard Open Finance"
    )
    parser.add_argument("--receiver", "-r", metavar="NOME", action="append",
                        help="Filtrar por receptor (pode repetir: -r 'Itaú' -r 'BTG')")
    parser.add_argument("--all-orgs", action="store_true",
                        help="Buscar todas as organizações")
    parser.add_argument("--list-orgs", action="store_true",
                        help="Listar organizações disponíveis e sair")
    parser.add_argument("--months", type=int, metavar="N", help="Últimos N meses (ex: 6)")
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--output", "-o", metavar="FILE", help="Destino do JSON de saída")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Unique Consents — Open Finance Brasil[/bold]\n"
        "[dim]Consentimentos únicos (CPF + CNPJ) por receptor/transmissor[/dim]",
        border_style="blue",
    ))

    # resolve_date_range retorna None se sem args → usa default de 90 dias do browser
    dates = resolve_date_range(args.months, args.start, args.end) or \
            resolve_date_range(months=3, start=None, end=None)

    result = run_session(
        org_names=args.receiver,
        all_orgs=args.all_orgs,
        dates=dates,
        list_orgs=args.list_orgs,
    )

    if args.list_orgs:
        table = Table(title=f"Organizações disponíveis ({len(result['orgs'])})")
        table.add_column("Label", style="cyan")
        table.add_column("UUID", style="dim")
        for o in result["orgs"]:
            table.add_row(o["label"], o["value"])
        console.print(table)
        return

    records = result["data"]
    if records:
        title = f"Consentimentos Únicos — {records[0]['org']}"
        _render_consents(records, title)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = args.output or str(
            OUTPUT_DIR / f"unique_consents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        save_json(records, output_file)
        console.print(f"\n[bold green]✓ {len(records)} registros salvos em {output_file}[/bold green]")
    else:
        console.print("[yellow]Nenhum dado capturado.[/yellow]")


if __name__ == "__main__":
    main()
