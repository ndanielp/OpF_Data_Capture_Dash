"""
MCP Server — Open Finance Brasil Dashboard
==========================================
Expõe as estratégias de extração do poc.py como tools MCP para uso no Claude.

Tools disponíveis:
  • get_api_requests_evolution      — HTML/RSC scraping (sem filtros, mais confiável)
  • get_organisations_and_apis      — Lista organizações, APIs e endpoints disponíveis
  • get_api_requests_filtered       — Gráfico filtrado via /api/api-requests
  • get_data_updated_at             — Data de atualização dos dados no dashboard
  • get_fridays_in_period           — Calcula sextas-feiras num período (helper de datas)

Uso:
  python mcp_server.py              (modo stdio, padrão para Claude Code)

Registro no Claude Code:
  claude mcp add openfinance python /caminho/para/mcp_server.py
"""

import json
import httpx
from mcp.server.fastmcp import FastMCP

from poc import (
    strategy_html_scraping,
    strategy_internal_api,
    strategy_chart_with_filters,
    get_fridays_in_period,
    BASE_URL,
    EVOLUTION_PATH,
    HEADERS_JSON,
    PHASE,
    COLLECTION,
)

mcp = FastMCP(
    "openfinance",
    instructions=(
        "Ferramentas para extrair dados do Dashboard Open Finance Brasil "
        "(https://dashboard.openfinancebrasil.org.br). "
        "Use get_api_requests_evolution para dados gerais de evolução de chamadas. "
        "Use get_organisations_and_apis para descobrir IDs de filtros válidos. "
        "Use get_api_requests_filtered para dados segmentados por API, status, etc."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — Evolução sem filtros (RSC scraping)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_api_requests_evolution() -> list[dict]:
    """
    Retorna a série histórica semanal de chamadas de API do Open Finance Brasil.

    Usa HTML/RSC scraping (Estratégia 1) — funciona sem autenticação ou cookies.
    Os dados são indexados por sexta-feira e cobrem o histórico disponível no dashboard.

    Retorna lista de dicts com: date (YYYY-MM-DD), weekday, total, total_fmt.
    """
    with httpx.Client(http2=False, verify=True, timeout=30) as client:
        return strategy_html_scraping(client)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — Organizações e APIs disponíveis
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_organisations_and_apis() -> dict:
    """
    Lista todas as organizações (receptores e transmissores), APIs e endpoints
    disponíveis no Dashboard Open Finance Brasil.

    Use esta tool para descobrir os IDs válidos antes de chamar
    get_api_requests_filtered com filtros específicos.

    Retorna dict com chaves:
      - organisations_client: lista de receptores (consomem dados)
      - organisations_server: lista de transmissores (fornecem dados)
      - apis: lista de APIs disponíveis (com _id e label)
      - endpoints_sample: endpoints da primeira API como exemplo
      - updated_at: data de atualização dos dados
    """
    with httpx.Client(http2=False, verify=True, timeout=30) as client:
        return strategy_internal_api(client)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — Evolução filtrada via /api/api-requests
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_api_requests_filtered(
    apis: list[str] | None = None,
    endpoints: list[str] | None = None,
    receivers: list[str] | None = None,
    transmitters: list[str] | None = None,
    status: int | None = None,
    days: int = 90,
) -> list[dict]:
    """
    Retorna dados de evolução de chamadas com filtros específicos.

    Chama POST /api/api-requests — endpoint descoberto por engenharia reversa do JS.
    NOTA: sem filtros ativos retorna [] (comportamento do backend — dados sem filtros
    vêm via RSC; use get_api_requests_evolution para isso).

    Parâmetros:
      apis         — lista de IDs de API (ex: ["credit-cards-accounts"])
      endpoints    — lista de IDs de endpoint
      receivers    — lista de UUIDs de receptores (instituições que consomem dados)
      transmitters — lista de UUIDs de transmissores (instituições que fornecem dados)
      status       — filtrar por status HTTP: 200 (sucesso) ou 500 (erro)
      days         — janela temporal em dias (padrão: 90)

    Use get_organisations_and_apis primeiro para obter os IDs válidos.

    Retorna lista de dicts com: date (YYYY-MM-DD), total, total_fmt.
    """
    with httpx.Client(http2=False, verify=True, timeout=30) as client:
        return strategy_chart_with_filters(
            client,
            receivers=receivers,
            transmitters=transmitters,
            apis=apis,
            endpoints_filter=endpoints,
            status=status,
            days=days,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — Data de atualização dos dados
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_data_updated_at() -> dict | None:
    """
    Retorna a data em que os dados do dashboard foram atualizados pela última vez.

    Chama POST /api/updated-at com o pathname da página de evolução.
    Retorna dict com chave 'updatedAt' no formato ISO 8601, ou None se falhar.
    """
    url = f"{BASE_URL}/api/updated-at"
    body = {"pathname": EVOLUTION_PATH}
    try:
        with httpx.Client(http2=False, verify=True, timeout=15) as client:
            resp = client.post(
                url,
                content=json.dumps(body).encode(),
                headers=HEADERS_JSON,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — Helper de datas (sextas-feiras)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_fridays_in_period(days: int = 90) -> list[str]:
    """
    Retorna a lista de sextas-feiras nos últimos N dias (padrão: 90).

    Os dados do Open Finance são indexados semanalmente por sexta-feira.
    Use para entender quais datas serão consultadas antes de chamar
    get_api_requests_filtered.

    Retorna lista de strings ISO 8601 (ex: "2025-12-06T00:00:00.000Z").
    """
    return get_fridays_in_period(days)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
