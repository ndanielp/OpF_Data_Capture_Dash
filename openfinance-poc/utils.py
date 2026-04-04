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

def _default_chromium_bin() -> str | None:
    """Retorna o caminho do Chromium instalado pelo Playwright, ou None para usar o padrão."""
    if os.name == "nt":
        # Windows: caminho padrão do Playwright
        candidates = sorted(
            (Path.home() / "AppData/Local/ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"),
            reverse=True,
        )
        return str(candidates[0]) if candidates else None
    # Linux/Mac: deixa o Playwright resolver automaticamente
    return None


CHROMIUM_BIN = os.environ.get("CHROMIUM_BIN") or _default_chromium_bin()
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
# Browser anti-detecção
# ─────────────────────────────────────────────────────────────────────────────

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
"""


def create_browser(p):
    """Lança Chromium com flags anti-detecção e sem cache em disco."""
    kwargs = dict(
        headless=True,
        proxy=get_proxy(),
        args=[
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-application-cache",
            "--disable-cache",
            "--disk-cache-size=0",
        ],
    )
    if CHROMIUM_BIN:
        kwargs["executable_path"] = CHROMIUM_BIN
    return p.chromium.launch(**kwargs)


def create_page(browser):
    """Cria página com User-Agent real e webdriver escondido."""
    ctx = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1440, "height": 900},
        locale="pt-BR",
        user_agent=_USER_AGENT,
        extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
    )
    page = ctx.new_page()
    page.add_init_script(_INIT_SCRIPT)
    return page


def close_browser_clean(browser, page) -> None:
    """
    Limpa cookies, localStorage/sessionStorage e cache HTTP (via Cache API)
    do contexto da página, fecha o contexto e depois o browser.
    Garante estado completamente limpo a cada receptor.
    """
    try:
        ctx = page.context
        ctx.clear_cookies()
        try:
            page.evaluate(
                "() => { "
                "  try { localStorage.clear(); } catch(_) {} "
                "  try { sessionStorage.clear(); } catch(_) {} "
                "  try { caches.keys().then(ks => ks.forEach(k => caches.delete(k))); } catch(_) {} "
                "}"
            )
        except Exception:
            pass
        ctx.close()
    except Exception:
        pass
    finally:
        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# Navegação com retry
# ─────────────────────────────────────────────────────────────────────────────

def goto_with_retry(page, url: str, selector: str, max_retries: int = 3) -> None:
    """
    Navega para URL e aguarda selector aparecer, com até max_retries tentativas.
    - 403 CloudFront: backoff longo (60s, 120s) para aguardar fim do rate limit.
    - Outros erros: backoff curto (3s, 6s).
    """
    for attempt in range(max_retries):
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=45000)
            if resp and resp.status == 403:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        "Portal bloqueou a requisição (403 CloudFront). "
                        "Aguarde alguns minutos e tente novamente com menos workers."
                    )
                wait_ms = 60_000 * (attempt + 1)   # 60s, 120s
                page.wait_for_timeout(wait_ms)
                continue
            page.wait_for_selector(selector, timeout=15000)
            return
        except RuntimeError:
            raise
        except Exception:
            if attempt == max_retries - 1:
                raise
            page.wait_for_timeout(3000 * (attempt + 1))


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
