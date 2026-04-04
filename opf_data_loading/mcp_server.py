"""
mcp_server.py — MCP Server: OpF Data Loading
=============================================
Expõe o pipeline de coleta como tools MCP para uso no Claude Code ou
qualquer LLM compatível com o Model Context Protocol.

Tools disponíveis:
  • run_collection  — Executa coleta completa + upsert CSV em data/
  • get_last_run    — Resumo e log da última execução
  • preview_csv     — Visualiza últimas N linhas de um CSV local
  • get_data_status — Lista CSVs em data/ com estatísticas

Uso (stdio, padrão MCP):
  python mcp_server.py

Registro no .mcp.json:
  {
    "mcpServers": {
      "opf-data-loading": {
        "command": "python",
        "args": ["/home/user/Claude_Projects/opf_data_loading/mcp_server.py"]
      }
    }
  }
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pandas as pd
from mcp.server.fastmcp import FastMCP

import config
from collector import run_collection as _run_collection

mcp = FastMCP(
    "opf-data-loading",
    instructions=(
        "Ferramentas para coleta e exportação de dados do Open Finance Brasil. "
        "Use run_collection para coletar dados e salvar CSVs localmente em data/. "
        "Use get_data_status para verificar o estado atual dos CSVs. "
        "Use preview_csv para visualizar dados antes de uma análise. "
        "Use get_last_run para inspecionar o log da última execução."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — Coleta completa
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def run_collection(
    start_date: str = "4w",
    end_date: str = "today",
    workers: int = 3,
) -> dict:
    """
    Executa o pipeline completo de coleta de dados do Open Finance Brasil.

    O processo:
      1. Coleta consentimentos únicos (CPF/CNPJ) por receptor via Playwright
      2. Coleta chamadas de API por receptor × API × status
      3. Faz upsert dos dados em data/consents.csv e data/api_requests.csv (sem duplicatas)
      4. Salva logs detalhados por receptor em logs/{receptor}/YYYY-MM-DD_HH-MM-SS.log

    Parâmetros:
      start_date — início do período. Formatos: "4w" (4 semanas), "3m" (3 meses),
                   "YYYY-MM-DD". Padrão: "4w"
      end_date   — fim do período. "today" ou "YYYY-MM-DD". Padrão: "today"
      workers    — browsers paralelos (padrão: 3; reduza para 1-2 se houver erro 403)

    Retorna dict com: run_id, period, weeks, receptors,
    n_consents_db, n_api_db, n_new_consents, n_new_api, duration_s.
    """
    return _run_collection(start_date=start_date, end_date=end_date, workers=workers)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — Última execução
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_last_run() -> dict:
    """
    Retorna o log da última execução (logs/_global/*.log mais recente).

    Retorna dict com: run_id, log_path, lines (últimas 50 linhas do log).
    """
    log_dir = config.LOG_DIR / "_global"
    if not log_dir.exists():
        return {"error": "Nenhuma execução encontrada. Execute run_collection primeiro."}

    log_files = sorted(log_dir.glob("*.log"), reverse=True)
    if not log_files:
        return {"error": "Nenhum log encontrado em logs/_global/"}

    latest = log_files[0]
    lines = latest.read_text(encoding="utf-8").splitlines()
    return {
        "run_id":   latest.stem,
        "log_path": str(latest),
        "lines":    lines[-50:],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — Preview CSV
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def preview_csv(dataset: str = "consents", rows: int = 10) -> list[dict]:
    """
    Visualiza as últimas N linhas de um CSV local em data/.

    Parâmetros:
      dataset — "consents" ou "api_requests"
      rows    — número de linhas a retornar (padrão: 10)

    Retorna lista de dicts com os dados do CSV.
    """
    name = "consents.csv" if dataset == "consents" else "api_requests.csv"
    csv_path = config.DATA_DIR / name

    if not csv_path.exists():
        return [{"info": f"{name} ainda não existe. Execute run_collection primeiro."}]

    df = pd.read_csv(csv_path)
    return df.tail(rows).to_dict(orient="records")


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — Status local
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_data_status() -> dict:
    """
    Resume o estado atual dos dados locais em data/ e logs/.

    Retorna para cada CSV: total de linhas, período coberto, receptores distintos.
    Também lista execuções recentes em logs/_global/.
    """
    status: dict = {
        "data_dir": str(config.DATA_DIR),
        "log_dir":  str(config.LOG_DIR),
    }

    for name, pk in [("consents.csv", "receptor_uuid"), ("api_requests.csv", "receptor_uuid")]:
        csv_path = config.DATA_DIR / name
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            status[name] = {
                "rows":       len(df),
                "date_min":   str(df["date"].min()) if "date" in df.columns else None,
                "date_max":   str(df["date"].max()) if "date" in df.columns else None,
                "receptors":  int(df[pk].nunique()) if pk in df.columns else None,
            }
        else:
            status[name] = {"exists": False}

    log_global = config.LOG_DIR / "_global"
    if log_global.exists():
        runs = sorted(log_global.glob("*.log"), reverse=True)
        status["recent_runs"] = [f.stem for f in runs[:5]]
    else:
        status["recent_runs"] = []

    return status


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
