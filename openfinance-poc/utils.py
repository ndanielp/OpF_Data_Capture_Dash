"""
utils.py — Utilitários compartilhados
======================================
Funções e constantes usadas por api_requests.py e unique_consents.py.
"""

import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console(legacy_windows=False)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

CHROMIUM_BIN = os.environ.get(
    "CHROMIUM_BIN",
    str(Path.home() / "AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe")
    if os.name == "nt"
    else "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
)
OUTPUT_DIR = Path("data/exports")
BASE_URL = "https://dashboard.openfinancebrasil.org.br"


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
# Datas
# ─────────────────────────────────────────────────────────────────────────────

def fridays_between(start: datetime, end: datetime) -> list[str]:
    """Retorna todas as sextas-feiras entre start e end como ISO strings UTC."""
    result = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end_utc = end.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    while current <= end_utc:
        if current.weekday() == 4:  # Friday
            result.append(current.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        current += timedelta(days=1)
    return result


def resolve_date_range(
    months: int | None,
    start: str | None,
    end: str | None,
) -> list[str] | None:
    """
    Converte argumentos de data em lista de sextas-feiras.
    Retorna None quando nenhum argumento é fornecido — sinaliza ao chamador
    para usar o período default do browser (90 dias).
    """
    today = datetime.now(timezone.utc)

    if start or end:
        s = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if start else today - timedelta(days=90)
        e = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else today
    elif months:
        s = today - timedelta(days=months * 30)
        e = today
    else:
        return None  # sinaliza "usar default do browser"

    fridays = fridays_between(s, e)
    if not fridays:
        console.print("[yellow]⚠ Nenhuma sexta-feira encontrada no período informado.[/yellow]")
    return fridays


# ─────────────────────────────────────────────────────────────────────────────
# Parse de datas
# ─────────────────────────────────────────────────────────────────────────────

def parse_record_date(raw: str) -> str:
    """
    Converte qualquer formato de data usado pela API para YYYY-MM-DD.
    Trata o prefixo RSC '$D' e strings ISO com sufixo 'Z'.
    """
    raw = str(raw).lstrip("$D")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

def save_json(data: list | dict, filename: str) -> str:
    """Salva data em JSON. Cria diretórios intermediários se necessário. Retorna o caminho."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"[dim]  → {path}[/dim]")
    return str(path)


def render_table(records: list[dict], title: str, columns: list[tuple]) -> None:
    """
    Renderiza uma tabela Rich.

    columns: lista de (chave, label, justify, style)
      ex: [("date", "Data", "left", "cyan"), ("total", "Total", "right", "green")]
    """
    if not records:
        console.print("[yellow]Nenhum dado para exibir.[/yellow]")
        return
    table = Table(title=title, show_lines=True)
    for key, label, justify, style in columns:
        table.add_column(label, justify=justify, style=style, no_wrap=(justify == "left"))
    for r in records:
        row = []
        for key, *_ in columns:
            val = r.get(key, "—")
            row.append(f"{val:,}" if isinstance(val, int) else str(val))
        table.add_row(*row)
    console.print(table)
