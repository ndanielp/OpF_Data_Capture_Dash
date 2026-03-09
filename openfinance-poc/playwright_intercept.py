"""
Playwright Interceptor — Dashboard Open Finance Brasil
======================================================
Abre o browser headless, navega até a página de evolução de chamadas,
aplica filtros programaticamente e intercepta as respostas de /api/api-requests.

Uso:
  python3 playwright_intercept.py
  python3 playwright_intercept.py --api credit-cards-accounts
  python3 playwright_intercept.py --api loans --status 200
  python3 playwright_intercept.py --list-filters
"""

import json
import time
import argparse
import urllib.parse
import os
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Response
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

BASE_URL = "https://dashboard.openfinancebrasil.org.br"
EVOLUTION_URL = f"{BASE_URL}/transactional-data/api-requests/evolution"
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
# Interceptação de respostas
# ─────────────────────────────────────────────────────────────────────────────

def make_response_handler(captured: list):
    """Retorna handler que captura respostas de /api/api-requests."""
    def handler(response: Response):
        if "/api/api-requests" in response.url and response.status == 200:
            try:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    console.print(
                        f"[green]✓[/green] Interceptado: {len(data)} pontos de dados "
                        f"de [dim]{response.url}[/dim]"
                    )
                    captured.append({
                        "url": response.url,
                        "data": data,
                        "captured_at": datetime.now().isoformat(),
                    })
            except Exception:
                pass
    return handler


def make_request_handler(requests_log: list):
    """Loga todos os POSTs para /api/* para debug."""
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
# Interação com filtros via Playwright
# ─────────────────────────────────────────────────────────────────────────────

FILTER_LABELS = {
    "receivers":    "Receptores",
    "transmitters": "Transmissores",
    "apis":         "APIs",
    "endpoints":    "Endpoints",
    "status":       "Status",
}


def _get_control(page: Page, label: str, timeout: int = 5000):
    """
    Localiza o react-select control pelo label acima dele.
    Estrutura real do DOM:
      <div class="css-48dm8r">          ← contém o label como primeiro texto
        <p>APIs</p>                     ← label
        <div class="css-fyq6mk-container">
          <div class="css-13cymwt-control"> ← este é o alvo
    """
    selector = f"div.css-48dm8r:has-text('{label}') .css-13cymwt-control, " \
               f"div.css-48dm8r:has-text('{label}') [class*='control']"
    return page.locator(selector).first


def select_filter(page: Page, filter_key: str, option_value: str, timeout: int = 8000):
    """
    Seleciona um valor em um dropdown react-select pelo key do filtro.
    filter_key: 'apis' | 'receivers' | 'transmitters' | 'endpoints'
    option_value: texto visível da opção (label) para busca.
    """
    label = FILTER_LABELS.get(filter_key, filter_key)
    console.print(f"  [dim]Aplicando filtro '{label}' = '{option_value}'[/dim]")

    try:
        ctrl = _get_control(page, label, timeout)
        ctrl.click(timeout=timeout)
        page.wait_for_timeout(500)

        # Digitar para filtrar opções
        page.keyboard.type(option_value[:20], delay=60)
        page.wait_for_timeout(1200)

        # Clicar na primeira opção visível
        option_sel = (
            f"div.css-48dm8r:has-text('{label}') [class*='option']"
        )
        opt = page.locator(option_sel).first
        opt.click(timeout=timeout)
        console.print(f"  [green]✓[/green] '{label}' = '{option_value}' aplicado")
        return True
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Filtro '{label}' falhou: {e}")
        return False


def click_status_filter(page: Page, status: int, timeout: int = 8000):
    """Seleciona Sucesso (200) ou Falha (500) no filtro de status."""
    label_status = "Sucesso" if status == 200 else "Falha"
    console.print(f"  [dim]Aplicando Status = '{label_status}'[/dim]")

    try:
        ctrl = _get_control(page, "Status", timeout)
        ctrl.click(timeout=timeout)
        page.wait_for_timeout(500)

        option = page.locator(
            f"div.css-48dm8r:has-text('Status') [class*='option']:has-text('{label_status}')"
        ).first
        option.click(timeout=timeout)
        console.print(f"  [green]✓[/green] Status = '{label_status}' aplicado")
        return True
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Filtro Status falhou: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Sessão principal
# ─────────────────────────────────────────────────────────────────────────────

def run_session(
    api_filter: str | None = None,
    receiver_filter: str | None = None,
    transmitter_filter: str | None = None,
    status_filter: int | None = None,
    list_filters: bool = False,
    screenshot: bool = True,
) -> list[dict]:
    """
    Abre o browser, navega para a página, aplica filtros e coleta dados interceptados.
    Retorna lista de datasets capturados.
    """
    captured = []
    requests_log = []
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

        # Registrar interceptadores
        page.on("response", make_response_handler(captured))
        page.on("request", make_request_handler(requests_log))

        # ── Navegar ──
        console.print(f"[dim]Navegando para {EVOLUTION_URL}[/dim]")
        page.goto(EVOLUTION_URL, wait_until="networkidle", timeout=45000)
        console.print(f"[green]✓[/green] Página carregada: [cyan]{page.title()}[/cyan]")

        if screenshot:
            page.screenshot(path="screenshot_inicial.png", full_page=False)
            console.print("[dim]  → screenshot_inicial.png[/dim]")

        # ── Listar filtros disponíveis ──
        if list_filters:
            console.rule("[bold]Filtros disponíveis na página")
            filters = page.locator("[filter]").all()
            for f in filters:
                fname = f.get_attribute("filter")
                options = f.locator("[class*='option']").all_text_contents()
                console.print(f"  [cyan]{fname}[/cyan]: {options[:5]}")

        # ── Aguardar elementos de filtro carregarem ──
        page.wait_for_selector("div.css-48dm8r:has-text('APIs') [class*='control']", timeout=15000)
        console.print("[green]✓[/green] Filtros carregados")

        # ── Aplicar filtros ──
        if api_filter:
            select_filter(page, "apis", api_filter)
            page.wait_for_timeout(2000)

        if receiver_filter:
            select_filter(page, "receivers", receiver_filter)
            page.wait_for_timeout(2000)

        if transmitter_filter:
            select_filter(page, "transmitters", transmitter_filter)
            page.wait_for_timeout(2000)

        if status_filter:
            click_status_filter(page, status_filter)
            page.wait_for_timeout(2000)

        # ── Aguardar resposta da API após filtros ──
        if any([api_filter, receiver_filter, transmitter_filter, status_filter]):
            console.print("[dim]Aguardando atualização do gráfico...[/dim]")
            page.wait_for_timeout(4000)

            if screenshot:
                page.screenshot(path="screenshot_filtrado.png", full_page=False)
                console.print("[dim]  → screenshot_filtrado.png[/dim]")

        # ── Extrair dados do DOM também (fallback) ──
        # O gráfico Nivo expõe os dados em atributos aria-label dos paths SVG
        dom_data = extract_chart_from_dom(page)

        browser.close()

    # ── Processar resultados ──
    all_results = []

    if captured:
        for capture in captured:
            records = parse_api_response(capture["data"])
            all_results.extend(records)
            _render_table(records, f"Dados interceptados de {capture['url'].split('/')[-1]}")
    elif dom_data:
        console.print("[yellow]→ API não interceptada; usando dados do DOM SVG[/yellow]")
        all_results = dom_data
        _render_table(dom_data, "Dados extraídos do gráfico SVG (DOM)")
    else:
        console.print("[yellow]⚠ Nenhum dado capturado via intercepção ou DOM[/yellow]")

    # Salvar log de requests
    if requests_log:
        _save_json(requests_log, "requests_log.json")
        console.print(f"[dim]  → {len(requests_log)} POSTs registrados em requests_log.json[/dim]")

    return all_results


def extract_chart_from_dom(page: Page) -> list[dict]:
    """
    Fallback: extrai dados diretamente do SVG do gráfico Nivo via JavaScript.
    O Nivo renderiza <path> com atributo aria-label contendo "x: <date>, y: <value>".
    """
    try:
        data = page.evaluate("""() => {
            // Nivo chart data from SVG paths with aria-label
            const paths = document.querySelectorAll('[aria-label]');
            const results = [];
            paths.forEach(el => {
                const label = el.getAttribute('aria-label') || '';
                const match = label.match(/x:\\s*([\\d\\-T:.Z]+),\\s*y:\\s*([\\d.]+)/);
                if (match) {
                    results.push({ date: match[1], total: parseFloat(match[2]) });
                }
            });
            // Also try data from React fiber (internal state)
            return results;
        }""")
        if data:
            console.print(f"[green]✓[/green] {len(data)} pontos extraídos do SVG DOM")
            return [{"date": d["date"][:10], "total": int(d["total"]),
                     "total_fmt": f"{int(d['total']):,}"} for d in data]
    except Exception as e:
        console.print(f"[dim]DOM extraction: {e}[/dim]")
    return []


def parse_api_response(data: list) -> list[dict]:
    records = []
    for item in data:
        raw = str(item.get("date") or item.get("_id") or "").lstrip("$D")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = raw
        total = item.get("total", 0)
        records.append({"date": date_str, "total": total, "total_fmt": f"{total:,}"})
    return sorted(records, key=lambda r: r["date"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_table(records: list[dict], title: str = "Resultados"):
    if not records:
        return
    table = Table(title=title, show_lines=True)
    table.add_column("Data", style="cyan", no_wrap=True)
    table.add_column("Total de Chamadas", justify="right", style="green")
    for r in records:
        table.add_row(r.get("date", "—"), r.get("total_fmt", str(r.get("total", "—"))))
    console.print(table)


def _save_json(data, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"[dim]  → {filename}[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrai dados filtrados do Dashboard Open Finance via Playwright"
    )
    parser.add_argument("--api", help="Filtrar por API (ex: 'credit-cards-accounts' ou 'Cartão')")
    parser.add_argument("--receiver", help="Filtrar por receptor (nome parcial do banco)")
    parser.add_argument("--transmitter", help="Filtrar por transmissor (nome parcial)")
    parser.add_argument("--status", type=int, choices=[200, 500], help="200=Sucesso, 500=Falha")
    parser.add_argument("--list-filters", action="store_true", help="Listar filtros disponíveis")
    parser.add_argument("--no-screenshot", action="store_true", help="Não salvar screenshots")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]Playwright Interceptor — Open Finance Brasil[/bold]\n"
        "[dim]Captura dados filtrados via intercepção de chamadas do browser[/dim]",
        border_style="blue",
    ))

    results = run_session(
        api_filter=args.api,
        receiver_filter=args.receiver,
        transmitter_filter=args.transmitter,
        status_filter=args.status,
        list_filters=args.list_filters,
        screenshot=not args.no_screenshot,
    )

    if results:
        output_file = f"intercepted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        _save_json(results, output_file)
        console.print(f"\n[bold green]✓ {len(results)} registros salvos em {output_file}[/bold green]")
    else:
        console.print("\n[yellow]Nenhum dado interceptado.[/yellow]")


if __name__ == "__main__":
    main()
