"""
Unique Consents Scraper — Dashboard Open Finance Brasil
=======================================================
Captura dados de consentimentos únicos (CPF + CNPJ) por receptor ou transmissor.

Uso:
  python3 unique_consents.py --list-orgs
  python3 unique_consents.py --receiver "BANCO BMG"
  python3 unique_consents.py --receiver "Itaú" --months 6
  python3 unique_consents.py --receiver "BTG" --start 2025-10-01 --end 2026-01-31
  python3 unique_consents.py --all-orgs --months 3        # itera todas as orgs
"""

import json
import argparse
import urllib.parse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

BASE_URL = "https://dashboard.openfinancebrasil.org.br"
PAGE_URL = f"{BASE_URL}/transactional-data/unique-consents/receivers"
CHROMIUM_BIN = "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome"


# ─────────────────────────────────────────────────────────────────────────────
# Proxy
# ─────────────────────────────────────────────────────────────────────────────

def get_proxy() -> dict | None:
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not proxy_url:
        return None
    p = urllib.parse.urlparse(proxy_url)
    return {
        "server": f"{p.scheme}://{p.hostname}:{p.port}",
        "username": p.username or "",
        "password": p.password or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Datas
# ─────────────────────────────────────────────────────────────────────────────

def fridays_between(start: datetime, end: datetime) -> list[str]:
    result = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end_utc = end.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    while current <= end_utc:
        if current.weekday() == 4:
            result.append(current.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        current += timedelta(days=1)
    return result


def resolve_date_range(months: int | None, start: str | None, end: str | None) -> list[str]:
    today = datetime.now(timezone.utc)
    if start or end:
        s = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if start else today - timedelta(days=90)
        e = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else today
    elif months:
        s = today - timedelta(days=months * 30)
        e = today
    else:
        s = today - timedelta(days=90)
        e = today
    return fridays_between(s, e)


# ─────────────────────────────────────────────────────────────────────────────
# Browser session
# ─────────────────────────────────────────────────────────────────────────────

def fetch_orgs(page) -> list[dict]:
    """Retorna lista de {value, label} de organizações disponíveis."""
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


def fetch_unique_consents(
    org_uuids: list[str],
    dates: list[str],
    page,
) -> list[dict]:
    """
    Dispara a chamada a /api/unique-consents para as orgs e datas especificadas.
    Usa route interception para injetar os parâmetros certos.
    """
    captured = []

    # Route: substitui datas e orgs no body do POST
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

    # Selecionar a primeira org no dropdown para disparar o fetch
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
    proxy = get_proxy()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            proxy=proxy,
            args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
        )
        page = ctx.new_page()

        orgs = fetch_orgs(page)
        console.print(f"[green]✓[/green] {len(orgs)} organizações carregadas")

        if list_orgs or not orgs:
            browser.close()
            return {"orgs": orgs, "data": []}

        # Resolver quais orgs buscar
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

        # Buscar todas as orgs de uma vez (passa lista de UUIDs)
        org_uuids = [o["value"] for o in target_orgs]
        raw = fetch_unique_consents(org_uuids, dates, page)

        browser.close()

    # Enriquecer com label da org (quando single-org)
    org_label = target_orgs[0]["label"] if len(target_orgs) == 1 else f"{len(target_orgs)} orgs"
    records = []
    for item in raw:
        raw_date = str(item.get("date") or item.get("_id") or "")
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = raw_date
        records.append({
            "date": date_str,
            "cpf": item.get("cpf", 0),
            "cnpj": item.get("cnpj", 0),
            "total": item.get("cpf", 0) + item.get("cnpj", 0),
            "org": org_label,
        })

    return {"orgs": orgs, "data": sorted(records, key=lambda r: r["date"])}


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_table(records: list[dict], title: str = "Consentimentos Únicos"):
    if not records:
        console.print("[yellow]Nenhum dado capturado.[/yellow]")
        return
    table = Table(title=title, show_lines=True)
    table.add_column("Data", style="cyan", no_wrap=True)
    table.add_column("CPF", justify="right", style="green")
    table.add_column("CNPJ", justify="right", style="blue")
    table.add_column("Total", justify="right", style="bold white")
    if len({r["org"] for r in records}) > 1:
        table.add_column("Org", style="dim")
    for r in records:
        row = [r["date"], f"{r['cpf']:,}", f"{r['cnpj']:,}", f"{r['total']:,}"]
        if len({rec["org"] for rec in records}) > 1:
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
                        help="Buscar todas as organizações (iteração)")
    parser.add_argument("--list-orgs", action="store_true",
                        help="Listar organizações disponíveis e sair")
    parser.add_argument("--months", type=int, metavar="N",
                        help="Últimos N meses (ex: 6)")
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--output", "-o", metavar="FILE",
                        help="Salvar resultado em JSON (ex: out.json)")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Unique Consents — Open Finance Brasil[/bold]\n"
        "[dim]Consentimentos únicos (CPF + CNPJ) por receptor/transmissor[/dim]",
        border_style="blue",
    ))

    dates = resolve_date_range(args.months, args.start, args.end)

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
        render_table(records, title=title)
        output_file = args.output or f"unique_consents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        console.print(f"\n[bold green]✓ {len(records)} registros salvos em {output_file}[/bold green]")
    else:
        console.print("[yellow]Nenhum dado capturado.[/yellow]")


if __name__ == "__main__":
    main()
