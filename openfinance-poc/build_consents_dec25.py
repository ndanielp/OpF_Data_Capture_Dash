"""
build_consents_dec25.py — Base de consentimentos únicos por receptor (dez/2025)
================================================================================
Coleta consentimentos únicos (CPF + CNPJ) de todos os receptores ao final de
cada semana de dezembro de 2025 (sextas-feiras: 05, 12, 19, 26/dez).

Usa page.evaluate() para chamar fetch() diretamente no contexto do browser,
evitando múltiplos reloads de página — uma sessão única para todas as orgs.

Uso:
  python3 build_consents_dec25.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Route
from rich.panel import Panel

from unique_consents import fetch_orgs
from utils import (
    BASE_URL, CHROMIUM_BIN, OUTPUT_DIR,
    console, get_proxy, resolve_date_range, parse_record_date, save_json,
    render_table,
)

PAGE_URL = f"{BASE_URL}/transactional-data/unique-consents/receivers"
API_URL  = f"{BASE_URL}/api/unique-consents"

DEC25_START = "2025-12-01"
DEC25_END   = "2025-12-31"


# ─────────────────────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────────────────────

def fetch_consents_for_org(page, org_uuid: str, dates: list[str]) -> list[dict]:
    """
    Intercepta POST /api/unique-consents via route handler e injeta org + datas.
    Recarrega a página para disparar a requisição natural do Next.js (com headers corretos).
    """
    captured: list[dict] = []

    def route_handler(route: Route, _uuid=org_uuid):
        try:
            body = json.loads(route.request.post_data or "{}")
            body["orgs"]  = [_uuid]
            body["dates"] = dates
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    page.route(API_URL, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/unique-consents" in r.url, timeout=30000
        ) as resp_info:
            page.reload(wait_until="networkidle", timeout=30000)
        data = resp_info.value.json()
        if isinstance(data, list):
            captured = data
    except Exception as e:
        console.print(f"  [yellow]Timeout/erro org {org_uuid}: {e}[/yellow]")
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


def save_csv(records: list[dict], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "receptor", "receptor_uuid", "cpf", "cnpj", "total"])
        writer.writeheader()
        writer.writerows(records)
    console.print(f"[dim]  → {p}[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────────────────────────────────────

def run(dates: list[str]) -> list[dict]:
    all_records: list[dict] = []

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

        # Carrega a página uma vez para obter cookies/sessão e lista de orgs
        orgs = fetch_orgs(page)
        console.print(f"[green]✓[/green] {len(orgs)} receptores carregados")
        console.print(f"[dim]Período: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)[/dim]\n")

        if not orgs:
            browser.close()
            return []

        for i, org in enumerate(orgs, 1):
            console.print(f"  [{i}/{len(orgs)}] {org['label']}", end=" ")
            raw = fetch_consents_for_org(page, org["value"], dates)
            records = build_records(raw, org)
            all_records.extend(records)
            console.print(f"[dim]→ {len(records)} semanas[/dim]")

        browser.close()

    return sorted(all_records, key=lambda r: (r["date"], r["receptor"]))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold]Consentimentos Únicos por Receptor — Dezembro/2025[/bold]\n"
        "[dim]Todas as organizações receptoras · 4 semanas (dez/25)[/dim]",
        border_style="blue",
    ))

    dates = resolve_date_range(months=None, start=DEC25_START, end=DEC25_END)
    if not dates:
        console.print("[red]Nenhuma sexta-feira encontrada em dez/25.[/red]")
        return

    console.print(f"[dim]Semanas alvo: {[d[:10] for d in dates]}[/dim]\n")

    records = run(dates)

    if not records:
        console.print("[yellow]Nenhum dado capturado.[/yellow]")
        return

    render_table(
        records[:20],  # preview das primeiras 20 linhas
        title=f"Consentimentos Únicos — Dez/2025 (preview {min(20, len(records))}/{len(records)})",
        columns=[
            ("date",     "Data",    "left",  "cyan"),
            ("receptor", "Receptor","left",  "white"),
            ("cpf",      "CPF",     "right", "green"),
            ("cnpj",     "CNPJ",    "right", "blue"),
            ("total",    "Total",   "right", "bold white"),
        ],
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = str(OUTPUT_DIR / f"consents_dec25_{ts}.json")
    csv_path  = str(OUTPUT_DIR / f"consents_dec25_{ts}.csv")

    save_json(records, json_path)
    save_csv(records, csv_path)

    console.print(
        f"\n[bold green]✓ {len(records)} registros salvos[/bold green]\n"
        f"  JSON → {json_path}\n"
        f"  CSV  → {csv_path}"
    )


if __name__ == "__main__":
    main()
