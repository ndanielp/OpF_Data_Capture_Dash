"""
POC — Extração de Dados: Dashboard Open Finance Brasil
======================================================
Estratégias implementadas e validadas:

  ✓  Estratégia 1 — HTML/RSC Scraping
       Extrai dados pré-renderizados diretamente do HTML (sem filtros).
       Os dados estão em JSON escapado dentro de tags <script> do RSC stream.
       Formato das datas: "$D2025-12-12T00:00:00.000Z" (serialização Next.js).

  ✓  Estratégia 2 — Endpoints POST Internos (descoberta de filtros)
       POST /api/organisations → lista receptores / transmissores (by role)
       POST /api/apis          → lista todas as APIs disponíveis
       POST /api/endpoints     → lista endpoints de APIs selecionadas
       POST /api/updated-at    → data de atualização dos dados

  ⚠  Estratégia 3 — Gráfico com filtros (/api/api-requests)
       O endpoint aceita requisições válidas e retorna HTTP 200 com [].
       A razão: os dados iniciais (sem filtros) vêm via RSC server-side.
       O /api/api-requests só é chamado pelo BROWSER quando o usuário
       altera filtros — requer contexto de sessão do cliente Next.js.
       O body exato descoberto via engenharia reversa está documentado abaixo.

Endpoints descobertos via análise dos chunks JS do Next.js:
  POST /api/organisations    body: {role, phase, collection}
  POST /api/apis             body: {phase}
  POST /api/endpoints        body: {phase, apis[]}
  POST /api/api-requests     body: {axis, phase, apis[], endpoints[], receivers[], transmitters[], status, dates[]}
  POST /api/updated-at       body: {pathname}

Ref: https://dashboard.openfinancebrasil.org.br/transactional-data/api-requests/evolution
"""

import re
import json
from datetime import datetime, timedelta, timezone

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

BASE_URL = "https://dashboard.openfinancebrasil.org.br"
EVOLUTION_PATH = "/transactional-data/api-requests/evolution"
PHASE = "transactional-data"
COLLECTION = "api_requests_weekly"

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": f"{BASE_URL}{EVOLUTION_PATH}",
}

HEADERS_JSON = {
    **HEADERS_BASE,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 1 — HTML / RSC Payload scraping (FUNCIONA ✓)
# ─────────────────────────────────────────────────────────────────────────────

def strategy_html_scraping(client: httpx.Client) -> list[dict]:
    """
    O Next.js App Router serializa os dados no RSC stream via self.__next_f.push().
    Os dados estão em JSON escapado dentro da tag <script>, com o seguinte formato:
      {\\"_id\\":\\"$D2025-12-12T00:00:00.000Z\\",\\"total\\":5728621353,...}

    O RSC serializa Date objects com o prefixo "$D" (RSC wire format).
    Este método extrai os dados sem precisar de filtros ou autenticação.
    """
    console.rule("[bold blue]Estratégia 1 — HTML / RSC Payload Scraping")
    console.print(f"[dim]GET {BASE_URL}{EVOLUTION_PATH}[/dim]")

    resp = client.get(
        f"{BASE_URL}{EVOLUTION_PATH}",
        headers=HEADERS_BASE,
        follow_redirects=True,
        timeout=30,
    )
    resp.raise_for_status()
    html = resp.text
    console.print(f"[green]✓[/green] HTTP {resp.status_code} — {len(html):,} bytes")

    # Regex exato para o formato RSC: \\"_id\\":\\"$D<ISO_DATE>\\",\\"total\\":<NUM>
    # O formato foi confirmado via dump hexadecimal do HTML
    pattern = (
        r'\\"_id\\":\\"'
        r'\$D'
        r'(\d{4}-\d{2}-\d{2}T[^\\]+)'
        r'\\",'
        r'\\"total\\":(\d+)'
    )
    matches = re.findall(pattern, html)

    records = []
    seen = set()
    for raw_date, raw_total in matches:
        if raw_date in seen:
            continue
        seen.add(raw_date)
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        total = int(raw_total)
        records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "weekday": dt.strftime("%A"),
            "total": total,
            "total_fmt": f"{total:,}",
        })

    records.sort(key=lambda r: r["date"])

    if records:
        console.print(f"[green]✓[/green] {len(records)} semanas encontradas")
        _render_table(records, title="Evolução de chamadas API (dados sem filtros)")
    else:
        console.print("[yellow]⚠[/yellow] Dados não encontrados — estrutura RSC pode ter mudado.")

    with open("raw_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    console.print("[dim]  → HTML salvo em raw_page.html[/dim]")

    return records


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 2 — Endpoints POST internos (FUNCIONA ✓)
# ─────────────────────────────────────────────────────────────────────────────

def _post(client: httpx.Client, path: str, body: dict, label: str = "") -> dict | list | None:
    url = f"{BASE_URL}{path}"
    console.print(f"[dim]  POST {path}[/dim]  {label}")
    try:
        resp = client.post(
            url,
            content=json.dumps(body, ensure_ascii=False).encode(),
            headers=HEADERS_JSON,
            timeout=20,
            follow_redirects=True,
        )
        color = "green" if resp.status_code < 400 else "red"
        status_icon = "✓" if resp.status_code < 400 else "✗"
        console.print(f"  [{color}]{status_icon} HTTP {resp.status_code}[/]")
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code >= 400:
            console.print(f"  [yellow]Erro: {resp.text[:250]}[/yellow]")
        return None
    except Exception as exc:
        console.print(f"  [red]Exceção: {exc}[/red]")
        return None


def strategy_internal_api(client: httpx.Client) -> dict:
    """
    Descobre todos os valores válidos de filtro consultando os endpoints internos.
    Estes endpoints são chamados pelo frontend para popular os dropdowns.
    Retorna: receptores, transmissores, APIs, endpoints e data de atualização.
    """
    console.rule("[bold blue]Estratégia 2 — Endpoints de Filtro Internos")
    results = {}

    # Receptores (instituições que CONSOMEM dados)
    orgs_client = _post(client, "/api/organisations", {
        "role": "client",
        "phase": PHASE,
        "collection": COLLECTION,
    }, "Receptores")
    results["organisations_client"] = orgs_client
    if orgs_client:
        console.print(f"  [green]→ {len(orgs_client)} receptores[/green]")
        _save_json(orgs_client, "organisations_client.json")

    # Transmissores (instituições que FORNECEM dados)
    orgs_server = _post(client, "/api/organisations", {
        "role": "server",
        "phase": PHASE,
        "collection": COLLECTION,
    }, "Transmissores")
    results["organisations_server"] = orgs_server
    if orgs_server:
        console.print(f"  [green]→ {len(orgs_server)} transmissores[/green]")
        _save_json(orgs_server, "organisations_server.json")

    # APIs disponíveis
    apis = _post(client, "/api/apis", {"phase": PHASE}, "APIs")
    results["apis"] = apis
    if apis:
        console.print(f"  [green]→ {len(apis)} APIs disponíveis[/green]")
        _save_json(apis, "apis.json")

        # Endpoints de cada API (exemplo: primeira API)
        if isinstance(apis, list) and apis:
            first_api = apis[0]
            api_id = first_api.get("_id") or first_api.get("value")
            api_name = first_api.get("label", api_id)
            eps = _post(client, "/api/endpoints", {
                "phase": PHASE,
                "apis": [api_id],
            }, f"Endpoints de '{api_name}'")
            results["endpoints_sample"] = eps
            if eps:
                # Os endpoints retornam agrupados por grupo
                total_eps = (
                    sum(len(g.get("options", [])) for g in eps)
                    if isinstance(eps[0], dict) and "options" in eps[0]
                    else len(eps)
                )
                console.print(f"  [green]→ {total_eps} endpoints em '{api_name}'[/green]")
                _save_json(eps, "endpoints_sample.json")

    # Data de atualização dos dados
    updated = _post(client, "/api/updated-at", {
        "pathname": EVOLUTION_PATH
    }, "Data de atualização")
    results["updated_at"] = updated
    if updated:
        console.print(f"  [green]→ Dados de: [cyan]{updated.get('updatedAt', '?')}[/cyan][/green]")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA 3 — Gráfico filtrado via /api/api-requests (PARCIAL ⚠)
# ─────────────────────────────────────────────────────────────────────────────

def get_fridays_in_period(days: int = 90) -> list[str]:
    """
    Replica a função Jw(t) do frontend Next.js:
      - Calcula as últimas `days` dias a partir de hoje (UTC)
      - Retorna apenas as SEXTAS-FEIRAS nesse período
      - Os dados são indexados semanalmente por sexta-feira (getUTCDay() === 5)
    """
    today_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = today_utc - timedelta(days=days)
    fridays = []
    current = start
    while current <= today_utc:
        if current.weekday() == 4:  # 4 = Friday em Python
            fridays.append(current.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        current += timedelta(days=1)
    return fridays


def strategy_chart_with_filters(
    client: httpx.Client,
    receivers: list[str] | None = None,
    transmitters: list[str] | None = None,
    apis: list[str] | None = None,
    endpoints_filter: list[str] | None = None,
    status: int | None = None,
    days: int = 90,
    label: str = "",
) -> list[dict]:
    """
    Chama POST /api/api-requests — endpoint descoberto via engenharia reversa
    do chunk JS: static/chunks/86681-e120ab66b8397b55.js

    Body format (descoberto via minified JS):
      JSON.stringify({
        axis: "date",
        apis: a.apis,
        dates: a.dates,         ← array de Date ISO strings (sextas-feiras)
        endpoints: a.endpoints,
        phase: t.phase,
        receivers: a.receivers,
        transmitters: a.transmitters,
        status: a.status        ← número escalar: 200 ou 500 (não array!)
      })

    NOTA: O endpoint retorna [] quando chamado externamente sem filtros ativos.
    Na UI, só é chamado após o usuário alterar algum filtro (substituindo os
    dados iniciais do RSC). Para dados sem filtros, use strategy_html_scraping().
    """
    if label:
        console.rule(f"[bold blue]Estratégia 3 — {label}")
    else:
        console.rule("[bold blue]Estratégia 3 — /api/api-requests")

    dates = get_fridays_in_period(days)
    active_filters = {
        k: v for k, v in {
            "apis": apis,
            "endpoints": endpoints_filter,
            "receivers": receivers,
            "transmitters": transmitters,
            "status": status,
        }.items() if v is not None and v != []
    }
    console.print(f"  [dim]Filtros ativos: {active_filters or 'nenhum'}[/dim]")
    console.print(f"  [dim]Período: {days} dias ({len(dates)} sextas-feiras)[/dim]")

    body = {
        "axis": "date",
        "phase": PHASE,
        "apis": apis or [],
        "endpoints": endpoints_filter or [],
        "receivers": receivers or [],
        "transmitters": transmitters or [],
        "dates": dates,
    }
    if status is not None:
        body["status"] = status  # 200 ou 500, escalar

    data = _post(client, "/api/api-requests", body, "Evolução filtrada")

    if not data or not isinstance(data, list):
        console.print("  [yellow]⚠ Retornou vazio (típico sem cookies de sessão do browser)[/yellow]")
        return []

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

    records.sort(key=lambda r: r["date"])
    console.print(f"  [green]✓ {len(records)} pontos de dados[/green]")
    _render_table(records, title=f"Gráfico filtrado — {label or '/api/api-requests'}")
    _save_json(data, "chart_filtered.json")
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_table(records: list[dict], title: str = "Resultados"):
    if not records:
        return
    table = Table(title=title, show_lines=True)
    table.add_column("Data", style="cyan", no_wrap=True)
    if "weekday" in records[0]:
        table.add_column("Dia", style="dim")
    table.add_column("Total de Chamadas", justify="right", style="green")
    for r in records:
        row = [r.get("date", "—")]
        if "weekday" in r:
            row.append(r.get("weekday", ""))
        row.append(r.get("total_fmt", str(r.get("total", "—"))))
        table.add_row(*row)
    console.print(table)


def _save_json(data, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"  [dim]→ {filename}[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold]POC — Open Finance Brasil Dashboard[/bold]\n"
        "[dim]Extração programática de dados de chamadas de API[/dim]",
        border_style="blue",
    ))

    with httpx.Client(http2=False, verify=True) as client:

        # ── 1. HTML Scraping: dados sem filtros (RSC payload)
        html_data = strategy_html_scraping(client)
        console.print()

        # ── 2. Endpoints internos: lista de filtros disponíveis
        filter_data = strategy_internal_api(client)
        console.print()

        # ── 3. Tentativas de gráfico com filtros via /api/api-requests
        # Sem filtros
        all_data = strategy_chart_with_filters(
            client, days=90, label="Sem filtros"
        )
        console.print()

        # Filtrar por status de sucesso
        success_data = strategy_chart_with_filters(
            client, status=200, days=90, label="Somente sucesso (status=200)"
        )
        console.print()

        # Filtrar por status de falha
        error_data = strategy_chart_with_filters(
            client, status=500, days=90, label="Somente falhas (status=500)"
        )
        console.print()

        # Filtrar por API específica (Cartão de Crédito)
        api_data: list[dict] = []
        if filter_data.get("apis"):
            credit_api = next(
                (a for a in filter_data["apis"] if a.get("_id") == "credit-cards-accounts"),
                filter_data["apis"][0]
            )
            api_data = strategy_chart_with_filters(
                client,
                apis=[credit_api["_id"]],
                days=180,
                label=f"API: {credit_api.get('label', credit_api['_id'])}",
            )
            console.print()

        # ── Resumo ──
        console.rule("[bold green]Resumo Final")
        orgs_client = filter_data.get("organisations_client") or []
        orgs_server = filter_data.get("organisations_server") or []
        apis_list = filter_data.get("apis") or []

        summary = {
            "estrategia_1_html_scraping": {
                "funciona": len(html_data) > 0,
                "semanas_encontradas": len(html_data),
                "periodo": {
                    "inicio": html_data[0]["date"] if html_data else None,
                    "fim": html_data[-1]["date"] if html_data else None,
                },
                "total_chamadas": sum(r["total"] for r in html_data),
                "dados": html_data,
            },
            "estrategia_2_endpoints_filtro": {
                "funciona": len(orgs_client) > 0,
                "receptores_disponiveis": len(orgs_client),
                "transmissores_disponiveis": len(orgs_server),
                "apis_disponiveis": len(apis_list),
                "dados_atualizados_em": (filter_data.get("updated_at") or {}).get("updatedAt"),
            },
            "estrategia_3_api_requests": {
                "funciona": len(all_data) > 0,
                "nota": "Retorna [] sem filtros ativos — requer contexto do browser",
                "endpoint_descoberto": "/api/api-requests (POST)",
                "body_format": {
                    "axis": "date",
                    "phase": "transactional-data",
                    "apis": "array de IDs",
                    "endpoints": "array de IDs",
                    "receivers": "array de UUIDs",
                    "transmitters": "array de UUIDs",
                    "status": "200 ou 500 (escalar, não array!)",
                    "dates": "array de ISO strings (apenas sextas-feiras)",
                },
            },
        }

        _save_json(summary, "poc_summary.json")

        # Print resumo compacto
        compact = {k: {kk: vv for kk, vv in v.items() if kk != "dados"} for k, v in summary.items()}
        console.print_json(json.dumps(compact, ensure_ascii=False))

        console.print("\n[bold green]Arquivos gerados:[/bold green]")
        files = [
            ("raw_page.html", "HTML completo da página"),
            ("organisations_client.json", f"{len(orgs_client)} receptores"),
            ("organisations_server.json", f"{len(orgs_server)} transmissores"),
            ("apis.json", f"{len(apis_list)} APIs"),
            ("endpoints_sample.json", "Endpoints da primeira API"),
            ("chart_filtered.json", "Resposta do /api/api-requests"),
            ("poc_summary.json", "Resumo completo desta execução"),
        ]
        for fname, desc in files:
            console.print(f"  [cyan]•[/cyan] [bold]{fname}[/bold] — {desc}")


if __name__ == "__main__":
    main()
