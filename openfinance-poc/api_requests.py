"""
api_requests.py — Chamadas de API por período
==============================================
Captura volume semanal de chamadas do Dashboard Open Finance Brasil
via Playwright + route interception.

Uso:
  python3 api_requests.py
  python3 api_requests.py --api "Cartão" --months 6
  python3 api_requests.py --api loans --status 200
  python3 api_requests.py --start 2025-10-01 --end 2026-01-31 --status 500
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Response, Route
from rich.panel import Panel

from utils import (
    BASE_URL, CHROMIUM_BIN, OUTPUT_DIR,
    console, get_proxy, resolve_date_range, parse_record_date, save_json, render_table,
)

EVOLUTION_URL = f"{BASE_URL}/transactional-data/api-requests/evolution"

FILTER_LABELS = {
    "receivers":    "Receptores",
    "transmitters": "Transmissores",
    "apis":         "APIs",
    "endpoints":    "Endpoints",
    "status":       "Status",
}


# ─────────────────────────────────────────────────────────────────────────────
# Route handler
# ─────────────────────────────────────────────────────────────────────────────

def make_date_route_handler(custom_dates: list[str]):
    """Intercepta POST /api/api-requests e substitui o campo 'dates'."""
    def handler(route: Route):
        try:
            body = json.loads(route.request.post_data or "{}")
            original = body.get("dates", [])
            body["dates"] = custom_dates
            console.print(
                f"  [dim]Route: datas substituídas ({len(original)} → {len(custom_dates)} sextas)[/dim]"
            )
            route.continue_(post_data=json.dumps(body))
        except Exception as e:
            console.print(f"  [yellow]Route handler erro: {e}[/yellow]")
            route.continue_()
    return handler


# ─────────────────────────────────────────────────────────────────────────────
# Interceptação de respostas
# ─────────────────────────────────────────────────────────────────────────────

def make_response_handler(captured: list):
    def handler(response: Response):
        if "/api/api-requests" in response.url and response.status == 200:
            try:
                data = response.json()
                if isinstance(data, list) and data:
                    console.print(
                        f"[green]✓[/green] Interceptado: {len(data)} pontos de dados "
                        f"de [dim]{response.url}[/dim]"
                    )
                    captured.append({"url": response.url, "data": data,
                                     "captured_at": datetime.now().isoformat()})
            except Exception:
                pass
    return handler


def make_request_logger(requests_log: list):
    def handler(request):
        if "/api/" in request.url and request.method == "POST":
            try:
                body = json.loads(request.post_data or "{}")
            except Exception:
                body = {}
            requests_log.append({"url": request.url, "body": body})
            console.print(f"[dim]→ POST {request.url.replace(BASE_URL, '')}[/dim]")
    return handler


# ─────────────────────────────────────────────────────────────────────────────
# Filtros via DOM
# ─────────────────────────────────────────────────────────────────────────────

def _get_control(page: Page, label: str, timeout: int = 5000):
    selector = (
        f"div.css-48dm8r:has-text('{label}') .css-13cymwt-control, "
        f"div.css-48dm8r:has-text('{label}') [class*='control']"
    )
    return page.locator(selector).first


def select_filter(page: Page, filter_key: str, option_value: str, timeout: int = 8000):
    label = FILTER_LABELS.get(filter_key, filter_key)
    console.print(f"  [dim]Aplicando filtro '{label}' = '{option_value}'[/dim]")
    try:
        _get_control(page, label, timeout).click(timeout=timeout)
        page.wait_for_timeout(500)
        page.keyboard.type(option_value[:20], delay=60)
        page.wait_for_timeout(1200)
        page.locator(f"div.css-48dm8r:has-text('{label}') [class*='option']").first.click(timeout=timeout)
        console.print(f"  [green]✓[/green] '{label}' = '{option_value}' aplicado")
        return True
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Filtro '{label}' falhou: {e}")
        return False


def click_status_filter(page: Page, status: int, timeout: int = 8000):
    label_status = "Sucesso" if status == 200 else "Falha"
    console.print(f"  [dim]Aplicando Status = '{label_status}'[/dim]")
    try:
        _get_control(page, "Status", timeout).click(timeout=timeout)
        page.wait_for_timeout(500)
        page.locator(
            f"div.css-48dm8r:has-text('Status') [class*='option']:has-text('{label_status}')"
        ).first.click(timeout=timeout)
        console.print(f"  [green]✓[/green] Status = '{label_status}' aplicado")
        return True
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Filtro Status falhou: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Parse da resposta
# ─────────────────────────────────────────────────────────────────────────────

def parse_api_response(data: list) -> list[dict]:
    records = []
    for item in data:
        raw = str(item.get("date") or item.get("_id") or "")
        date_str = parse_record_date(raw)
        total = item.get("total", 0)
        records.append({"date": date_str, "total": total})
    return sorted(records, key=lambda r: r["date"])


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: extração via DOM SVG
# ─────────────────────────────────────────────────────────────────────────────

def extract_chart_from_dom(page: Page) -> list[dict]:
    try:
        data = page.evaluate("""() => {
            const paths = document.querySelectorAll('[aria-label]');
            const results = [];
            paths.forEach(el => {
                const label = el.getAttribute('aria-label') || '';
                const match = label.match(/x:\\s*([\\d\\-T:.Z]+),\\s*y:\\s*([\\d.]+)/);
                if (match) results.push({date: match[1], total: parseFloat(match[2])});
            });
            return results;
        }""")
        if data:
            console.print(f"[green]✓[/green] {len(data)} pontos extraídos do SVG DOM")
            return [{"date": d["date"][:10], "total": int(d["total"])} for d in data]
    except Exception as e:
        console.print(f"[dim]DOM extraction: {e}[/dim]")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Sessão principal
# ─────────────────────────────────────────────────────────────────────────────

def run_session(
    api_filter: str | None = None,
    receiver_filter: str | None = None,
    transmitter_filter: str | None = None,
    status_filter: int | None = None,
    custom_dates: list[str] | None = None,
    screenshot: bool = True,
) -> list[dict]:
    captured = []
    requests_log = []

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
        page.on("response", make_response_handler(captured))
        page.on("request", make_request_logger(requests_log))

        if custom_dates:
            console.print(
                f"  [dim]Período personalizado: {len(custom_dates)} sextas "
                f"({custom_dates[0][:10]} → {custom_dates[-1][:10]})[/dim]"
            )
            page.route(f"{BASE_URL}/api/api-requests", make_date_route_handler(custom_dates))

        console.print(f"[dim]Navegando para {EVOLUTION_URL}[/dim]")
        page.goto(EVOLUTION_URL, wait_until="networkidle", timeout=45000)
        console.print(f"[green]✓[/green] Página carregada: [cyan]{page.title()}[/cyan]")

        if screenshot:
            page.screenshot(path="screenshot_inicial.png")
            console.print("[dim]  → screenshot_inicial.png[/dim]")

        page.wait_for_selector("div.css-48dm8r:has-text('APIs') [class*='control']", timeout=15000)
        console.print("[green]✓[/green] Filtros carregados")

        for key, value in [
            ("apis", api_filter),
            ("receivers", receiver_filter),
            ("transmitters", transmitter_filter),
        ]:
            if value:
                select_filter(page, key, value)
                page.wait_for_timeout(2000)

        if status_filter:
            click_status_filter(page, status_filter)
            page.wait_for_timeout(2000)

        if any([api_filter, receiver_filter, transmitter_filter, status_filter]):
            console.print("[dim]Aguardando atualização do gráfico...[/dim]")
            page.wait_for_timeout(4000)
            if screenshot:
                page.screenshot(path="screenshot_filtrado.png")
                console.print("[dim]  → screenshot_filtrado.png[/dim]")

        dom_data = extract_chart_from_dom(page)
        browser.close()

    all_results = []
    cols = [("date", "Data", "left", "cyan"), ("total", "Total de Chamadas", "right", "green")]

    if captured:
        for capture in captured:
            records = parse_api_response(capture["data"])
            all_results.extend(records)
            render_table(records, f"Dados interceptados de {capture['url'].split('/')[-1]}", cols)
    elif dom_data:
        console.print("[yellow]→ API não interceptada; usando dados do DOM SVG[/yellow]")
        all_results = dom_data
        render_table(dom_data, "Dados extraídos do gráfico SVG (DOM)", cols)
    else:
        console.print("[yellow]⚠ Nenhum dado capturado via intercepção ou DOM[/yellow]")

    if requests_log:
        log_path = OUTPUT_DIR / "requests_log.json"
        save_json(requests_log, str(log_path))
        console.print(f"[dim]  → {len(requests_log)} POSTs registrados em {log_path}[/dim]")

    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrai volume semanal de chamadas de API do Dashboard Open Finance"
    )
    parser.add_argument("--api", help="Filtrar por API (ex: 'credit-cards-accounts' ou 'Cartão')")
    parser.add_argument("--receiver", help="Filtrar por receptor (nome parcial do banco)")
    parser.add_argument("--transmitter", help="Filtrar por transmissor (nome parcial)")
    parser.add_argument("--status", type=int, choices=[200, 500], help="200=Sucesso, 500=Falha")
    parser.add_argument("--months", type=int, metavar="N", help="Últimos N meses (ex: 6)")
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Data de início")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Data de fim (padrão: hoje)")
    parser.add_argument("--no-screenshot", action="store_true", help="Não salvar screenshots")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]API Requests — Open Finance Brasil[/bold]\n"
        "[dim]Volume semanal de chamadas via intercepção do browser[/dim]",
        border_style="blue",
    ))

    custom_dates = resolve_date_range(months=args.months, start=args.start, end=args.end)
    if custom_dates is not None:
        console.print(
            f"[dim]Período: {custom_dates[0][:10]} → {custom_dates[-1][:10]} "
            f"({len(custom_dates)} sextas)[/dim]"
        )

    results = run_session(
        api_filter=args.api,
        receiver_filter=args.receiver,
        transmitter_filter=args.transmitter,
        status_filter=args.status,
        custom_dates=custom_dates,
        screenshot=not args.no_screenshot,
    )

    if results:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / f"api_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(results, str(output_file))
        console.print(f"\n[bold green]✓ {len(results)} registros salvos em {output_file}[/bold green]")
    else:
        console.print("\n[yellow]Nenhum dado interceptado.[/yellow]")


if __name__ == "__main__":
    main()
