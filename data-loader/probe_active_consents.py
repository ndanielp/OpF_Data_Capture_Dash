"""
probe_active_consents.py — Diagnóstico do endpoint de consentimentos ativos.

Navega na página active-consents/receivers, intercepta todas as chamadas XHR/fetch
e exibe URL, método, request body e estrutura da resposta.

Uso:
    python probe_active_consents.py

Saída: imprime no terminal o(s) endpoint(s) chamados e a estrutura do payload.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from browser import BASE_URL
from session import OpFSession
from playwright.sync_api import sync_playwright

ACTIVE_CONSENTS_PAGE = f"{BASE_URL}/transactional-data/active-consents/receivers"
UNIQUE_CONSENTS_PAGE = f"{BASE_URL}/transactional-data/unique-consents/receivers"

# Receptor real para testar (colhido da resposta de /api/organisations)
# Será preenchido dinamicamente com o primeiro receptor retornado.
TEST_RECEPTOR = None
TEST_DATES = ["2026-05-12", "2026-05-19"]

# Candidatos de endpoint a testar por HTTP direto (após auth).
ENDPOINT_CANDIDATES = [
    "/api/active-consents",
    "/api/active_consents",
    "/api/consents/active",
    "/api/unique-consents",     # controle: sabemos que funciona
]

captured: list[dict] = []


def main():
    print(f"\n{'='*60}")
    print("Probe: active-consents endpoint — busca direta por HTTP")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        with OpFSession(p) as session:
            page = session._page

            # ── 1. Navega para capturar auth e a lista de receptores ──────────
            print("Passo 1: Navegando para capturar receptores...")
            orgs_captured: list[list] = []

            def on_org(response):
                if "/api/organisations" in response.url:
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            orgs_captured.append(data)
                    except Exception:
                        pass

            page.on("response", on_org)
            page.goto(ACTIVE_CONSENTS_PAGE, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            page.remove_listener("response", on_org)

            # Pega o primeiro receptor disponível.
            receptor = None
            for orgs in orgs_captured:
                if orgs:
                    receptor = orgs[0]
                    break

            if not receptor:
                print("  ERRO: nenhum receptor capturado de /api/organisations")
                return

            receptor_uuid = receptor["value"]
            receptor_name = receptor["label"]
            print(f"  Receptor de teste: {receptor_name} ({receptor_uuid})")

            # ── 2. Captura TODOS os requests enquanto navega na página ─────
            print("\nPasso 2: Interceptando todo o trafego de rede ao navegar...")
            all_requests: list[dict] = []

            def on_any_request(request):
                if request.method in ("POST", "GET") and "dashboard.openfinance" in request.url:
                    all_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "body": request.post_data,
                    })

            page.on("request", on_any_request)
            # Recarrega a página para capturar requests iniciais novamente.
            page.reload(wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.remove_listener("request", on_any_request)

            print(f"  Requests capturados: {len(all_requests)}")
            for r in all_requests:
                try:
                    body_parsed = json.loads(r["body"]) if r["body"] else None
                except Exception:
                    body_parsed = r["body"]
                print(f"  {r['method']} {r['url']}")
                if body_parsed:
                    print(f"    body: {json.dumps(body_parsed, ensure_ascii=False)[:200]}")

            # ── 3. Tenta endpoints candidatos adicionais via HTTP direto ──────
            extra_candidates = [
                "/api/active-consents",
                "/api/active-consents-weekly",
                "/api/consents-weekly",
                "/api/weekly-active-consents",
                "/api/receivers/active-consents",
                "/api/active",
                "/api/unique-consents",
            ]
            bodies_to_try = [
                {"dates": TEST_DATES, "orgs": [receptor_uuid], "role": "client"},
                {"dates": TEST_DATES, "receivers": [receptor_uuid]},
                {"dates": TEST_DATES, "orgs": [receptor_uuid], "role": "client", "collection": "consents_weekly"},
                {"dates": TEST_DATES, "receivers": [receptor_uuid], "role": "client"},
            ]

            print(f"\nPasso 3: Testando {len(extra_candidates)} endpoints x {len(bodies_to_try)} bodies...")
            for endpoint in extra_candidates:
                for body in bodies_to_try:
                    try:
                        result = session.post(endpoint, body)
                        if isinstance(result, list):
                            print(f"\n  *** SUCESSO: POST {endpoint}")
                            print(f"  *** Body usado: {json.dumps(body)}")
                            print(f"  *** Resposta: {len(result)} items")
                            if result:
                                print(f"  *** Primeiro: {json.dumps(result[0], ensure_ascii=False)[:400]}")
                            captured.append({
                                "url": endpoint,
                                "status": "ok",
                                "req_body": body,
                                "resp_sample": result[:2],
                            })
                            break  # encontrou — não testa mais bodies
                        elif isinstance(result, dict) and result:
                            print(f"  dict em {endpoint}: {json.dumps(result)[:200]}")
                    except Exception as exc:
                        err = str(exc)
                        if "404" not in err:
                            print(f"  {endpoint} [{json.dumps(body)[:60]}]: {type(exc).__name__}: {err[:80]}")
                print(".", end="", flush=True)
            print()

    # Resumo final
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    ok = [c for c in captured if c["status"] == "ok"]
    if ok:
        for c in ok:
            print(f"  ENDPOINT CONFIRMADO: POST {c['url']}")
            s = c.get("resp_sample") or []
            if s and isinstance(s[0], dict):
                print(f"  Chaves da resposta: {list(s[0].keys())}")
                print(f"  Amostra: {json.dumps(s[0], ensure_ascii=False)}")
    else:
        errs = [c for c in captured if c["status"] == "error"]
        print("  Nenhum endpoint respondeu com lista de dados.")
        for c in captured:
            status = c.get("status")
            err = c.get("error", "")[:100]
            print(f"  {c['url']}: {status} {err}")


if __name__ == "__main__":
    main()
