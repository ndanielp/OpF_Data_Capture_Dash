"""
test_probe.py — Testa se o endpoint aceita "apis": [] como probe
================================================================
Verifica dois receptores:
  - Banco CSF S/A  → esperado: zero chamadas
  - CIELO          → esperado: tem chamadas

Para cada receptor, testa três variantes do body:
  A) apis: []              (probe vazio)
  B) apis: null            (probe nulo)
  C) apis: ["consents"]    (controle — API específica conhecida)
"""

import json
import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright, Route

from utils import BASE_URL, CHROMIUM_BIN, get_proxy, resolve_date_range

PAGE_URL     = f"{BASE_URL}/transactional-data/api-requests/evolution"
API_ENDPOINT = f"{BASE_URL}/api/api-requests"
DB_PATH      = Path("data/consents.db")

RECEPTOR_DROPDOWN = "div.css-48dm8r:has-text('Receptores') [class*='control']"
RECEPTOR_OPTIONS  = "div.css-48dm8r:has-text('Receptores') [class*='option']"

TARGETS = ["Banco CSF S/A", "NUBANK"]

VARIANTS = [
    ("apis omitido",    {}),
    ("apis=[]",         {"apis": []}),
    ("apis=null",       {"apis": None}),
    ("apis=[consents]", {"apis": ["consents"]}),
]


def fetch_probe(page, receptor_uuid: str, extra_body: dict, dates: list[str],
                click_idx: int) -> list:
    """Dispara uma chamada com o body base + extra_body via route interception."""
    captured = []
    body = {
        "axis":      "date",
        "phase":     "transactional-data",
        "receivers": [receptor_uuid],
        "dates":     dates,
        "status":    200,
        **extra_body,
    }

    def handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    page.route(API_ENDPOINT, handler)
    try:
        with page.expect_response(
            lambda r: "/api/api-requests" in r.url, timeout=10000
        ) as resp_info:
            page.locator(RECEPTOR_DROPDOWN).first.click()
            page.wait_for_selector(RECEPTOR_OPTIONS, state="visible", timeout=8000)
            page.locator(RECEPTOR_OPTIONS).nth(click_idx).click()
        data = resp_info.value.json()
        if isinstance(data, list):
            captured = data
    except Exception as e:
        captured = [{"_error": str(e)}]
    finally:
        page.unroute(API_ENDPOINT, handler)
    return captured


def main():
    dates = resolve_date_range(months=1, start=None, end=None)
    print(f"Período: {dates[0][:10]} → {dates[-1][:10]}  ({len(dates)} semanas)\n")

    # Busca UUIDs no banco
    con = sqlite3.connect(str(DB_PATH))
    receptors = {}
    for name in TARGETS:
        row = con.execute(
            "SELECT receptor_uuid FROM unique_consents WHERE receptor LIKE ? LIMIT 1",
            (f"%{name}%",)
        ).fetchone()
        if row:
            receptors[name] = row[0]
            print(f"✓ {name}: {row[0]}")
        else:
            print(f"✗ {name}: não encontrado no banco")
    con.close()

    if not receptors:
        print("Nenhum receptor encontrado. Verifique o banco.")
        return

    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            proxy=get_proxy(),
            args=["--ignore-certificate-errors", "--no-sandbox"],
        )
        ctx  = browser.new_context(ignore_https_errors=True, locale="pt-BR")
        page = ctx.new_page()
        page.goto(PAGE_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_selector(RECEPTOR_DROPDOWN, timeout=15000)
        print("Página carregada.\n")

        click_idx = 0
        for rec_name, rec_uuid in receptors.items():
            print(f"{'─'*60}")
            print(f"Receptor: {rec_name}")
            print(f"UUID    : {rec_uuid}")
            for variant_label, extra_body in VARIANTS:
                data = fetch_probe(page, rec_uuid, extra_body, dates, click_idx)
                click_idx = 1 - click_idx

                n_items  = len(data)
                n_nonzero = sum(1 for d in data if isinstance(d, dict) and d.get("total", 0) > 0)
                error    = data[0].get("_error") if data and "_error" in data[0] else None

                if error:
                    status = f"ERRO: {error[:80]}"
                elif n_items == 0:
                    status = "[] vazio"
                else:
                    status = f"{n_items} itens, {n_nonzero} não-zero"
                    if n_nonzero > 0:
                        sample = next(d for d in data if d.get("total", 0) > 0)
                        status += f"  (ex: date={sample.get('date','?')}, total={sample.get('total','?')})"

                print(f"  {variant_label:<22} → {status}")
            print()

        browser.close()


if __name__ == "__main__":
    main()