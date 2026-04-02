"""
debug_api_requests.py — Testa body mínimo com apis + status + receiver
"""
import json
from playwright.sync_api import sync_playwright, Route
from utils import BASE_URL, CHROMIUM_BIN, get_proxy, resolve_date_range

PAGE_URL     = f"{BASE_URL}/transactional-data/api-requests/evolution"
API_ENDPOINT = f"{BASE_URL}/api/api-requests"

RECEPTOR_CONTROL = "div.css-48dm8r:has-text('Receptores') [class*='control']"
RECEPTOR_OPTIONS = "div.css-48dm8r:has-text('Receptores') [class*='option']"


def do_click(page, body_override, click_idx, label=""):
    captured = []

    def route_handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body_override))
        except Exception:
            route.continue_()

    def capture_response(resp):
        if "/api/api-requests" in resp.url:
            try:
                data = resp.json()
                n = len(data) if isinstance(data, list) else "N/A"
                sample = data[0] if (isinstance(data, list) and data) else None
                print(f"  [{label}] items={n}" + (f" first={sample}" if sample else ""))
                if isinstance(data, list):
                    captured.extend(data)
            except Exception as e:
                print(f"  [{label}] error: {e}")

    page.route(API_ENDPOINT, route_handler)
    page.on("response", capture_response)
    page.locator(RECEPTOR_CONTROL).first.click()
    page.wait_for_selector(RECEPTOR_OPTIONS, state="visible", timeout=10000)
    page.locator(RECEPTOR_OPTIONS).nth(click_idx).click()
    page.wait_for_timeout(4000)
    page.unroute(API_ENDPOINT, route_handler)
    page.remove_listener("response", capture_response)
    return captured


def run_debug(receptor_uuid: str, dates: list[str]):
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
        page.goto(PAGE_URL, wait_until="networkidle", timeout=60000)
        print("[INFO] Page loaded")

        # Test: minimal body (apis + status + receiver, no endpoints/transmitters)
        combos = [
            ("consents", 200), ("consents", 500),
            ("credit-cards-accounts", 200), ("credit-cards-accounts", 500),
            ("resources", 200), ("accounts", 200),
        ]
        for i, (api_id, status) in enumerate(combos):
            body = {
                "axis":      "date",
                "phase":     "transactional-data",
                "apis":      [api_id],
                "receivers": [receptor_uuid],
                "dates":     dates,
                "status":    status,
            }
            click_idx = i % 2
            r = do_click(page, body, click_idx, label=f"{api_id}/{status}")

        browser.close()


if __name__ == "__main__":
    import sqlite3
    con = sqlite3.connect("data/consents.db")
    rows = con.execute("""
        SELECT DISTINCT receptor, receptor_uuid FROM unique_consents
        WHERE total > 0 AND date BETWEEN '2025-12-01' AND '2025-12-31'
        ORDER BY total DESC LIMIT 1
    """).fetchall()
    con.close()
    print(f"Receptor: {rows[0][0]} ({rows[0][1]})")
    dates = resolve_date_range(None, "2025-12-01", "2025-12-31")
    print(f"Dates: {[d[:10] for d in dates]}")
    run_debug(rows[0][1], dates)
