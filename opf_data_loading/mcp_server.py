"""
mcp_server.py — MCP Server: OpF Data Loading
=============================================
Expõe o pipeline de coleta como tools MCP para uso no Claude Code ou
qualquer LLM compatível com o Model Context Protocol.

Tools disponíveis:
  • run_collection    — Executa coleta completa + upsert CSV no Drive
  • get_last_run      — Resumo da última execução
  • preview_csv       — Visualiza últimas N linhas de um CSV no Drive
  • get_drive_status  — Lista arquivos e estatísticas no Drive

Uso (stdio, padrão MCP):
  python mcp_server.py

Registro no Claude Code:
  claude mcp add opf-data-loading python /caminho/para/mcp_server.py

Ou no .mcp.json:
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

# Garante que o diretório do projeto está no path (necessário para imports locais)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from mcp.server.fastmcp import FastMCP

import config
import drive as drv
from collector import run_collection as _run_collection

mcp = FastMCP(
    "opf-data-loading",
    instructions=(
        "Ferramentas para coleta e exportação de dados do Open Finance Brasil. "
        "Use run_collection para coletar dados e exportar para o Google Drive. "
        "Use get_drive_status para verificar o estado atual dos arquivos no Drive. "
        "Use preview_csv para visualizar dados antes de uma análise. "
        "Use get_last_run para obter o resumo da última execução."
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
      3. Faz upsert dos dados em CSVs no Google Drive (sem duplicatas)
      4. Salva logs detalhados por receptor (local + Drive)

    Parâmetros:
      start_date — início do período. Formatos aceitos:
                   "4w" (últimas 4 semanas), "3m" (últimos 3 meses),
                   "YYYY-MM-DD" (data exata). Padrão: "4w"
      end_date   — fim do período. "today" ou "YYYY-MM-DD". Padrão: "today"
      workers    — número de browsers paralelos (padrão: 3; reduza se houver 403)

    Retorna dict com: run_id, period, weeks, receptors,
    n_consents_db, n_api_db, n_new_consents, n_new_api, duration_s.
    """
    return _run_collection(
        start_date=start_date,
        end_date=end_date,
        workers=workers,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — Última execução
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_last_run() -> dict:
    """
    Retorna o conteúdo do log da última execução (logs/_global/*.log).

    Lê o arquivo de log global mais recente e retorna suas últimas linhas,
    permitindo verificar o resultado sem precisar acessar o servidor.

    Retorna dict com: run_id, lines (lista de strings), log_path.
    """
    log_dir = config.LOCAL_LOG_DIR / "_global"
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
        "lines":    lines[-50:],  # últimas 50 linhas
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — Preview CSV
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def preview_csv(dataset: str = "consents", rows: int = 10) -> list[dict]:
    """
    Visualiza as últimas N linhas de um CSV no Google Drive.

    Parâmetros:
      dataset — "consents" ou "api_requests"
      rows    — número de linhas a retornar (padrão: 10)

    Retorna lista de dicts com os dados do CSV.
    Requer DRIVE_FOLDER_ID configurado no .env.
    """
    if not config.DRIVE_FOLDER_ID:
        return [{"error": "DRIVE_FOLDER_ID não configurado no .env"}]

    name = "consents.csv" if dataset == "consents" else "api_requests.csv"

    try:
        service = drv.get_service(config.SERVICE_ACCOUNT_FILE)
        df = drv.download_csv(service, config.DRIVE_FOLDER_ID, name)
    except Exception as exc:
        return [{"error": f"Falha ao baixar {name} do Drive: {exc}"}]

    if df is None:
        return [{"info": f"{name} ainda não existe no Drive. Execute run_collection primeiro."}]

    return df.tail(rows).to_dict(orient="records")


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — Status do Drive
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_drive_status() -> dict:
    """
    Verifica o estado atual dos arquivos no Google Drive.

    Retorna informações sobre:
      - consents.csv: total de linhas, período coberto, número de receptores
      - api_requests.csv: total de linhas, período coberto
      - Conectividade com o Drive (confirma auth da Service Account)

    Requer DRIVE_FOLDER_ID e SERVICE_ACCOUNT_FILE configurados no .env.
    """
    status: dict = {
        "drive_folder_id": config.DRIVE_FOLDER_ID or "(não configurado)",
        "service_account": str(config.SERVICE_ACCOUNT_FILE),
    }

    if not config.DRIVE_FOLDER_ID:
        status["error"] = "DRIVE_FOLDER_ID não configurado no .env"
        return status

    if not config.SERVICE_ACCOUNT_FILE.exists():
        status["error"] = f"Service account não encontrada: {config.SERVICE_ACCOUNT_FILE}"
        return status

    try:
        service = drv.get_service(config.SERVICE_ACCOUNT_FILE)
        status["auth"] = "ok"
    except Exception as exc:
        status["error"] = f"Falha na autenticação com Drive: {exc}"
        return status

    status["consents_csv"]    = drv.get_csv_stats(service, config.DRIVE_FOLDER_ID, "consents.csv")
    status["api_requests_csv"] = drv.get_csv_stats(service, config.DRIVE_FOLDER_ID, "api_requests.csv")
    status["files"]            = drv.list_files(service, config.DRIVE_FOLDER_ID)

    return status


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
