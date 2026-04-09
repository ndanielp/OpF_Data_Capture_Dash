"""
session.py — Sessão HTTP autenticada compartilhada contra o dashboard OpF
=========================================================================
Encapsula 1 browser Playwright + 1 page que passa pelo CloudFront (populando
cookies) e expõe `post()` / `get()` via `page.request`, que herda cookies e
headers do contexto automaticamente.

Substitui o padrão `page.route() + click no dropdown` de scrapers.py por
chamadas HTTP diretas, eliminando a dependência do DOM para disparar requests.

Uso típico:

    with sync_playwright() as p:
        with OpFSession(p, logger=log) as session:
            data = session.post("/api/unique-consents", {"dates": [...], "orgs": [...]})

Exceções classificadas:
- OpFTransientError: retenta (5xx, timeout, 401/403 pós-refresh, erros de rede)
- OpFFatalError:     aborta    (4xx não-auth, JSON inválido, schema inesperado)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from browser import BASE_URL, create_browser, create_page, goto_with_retry


# ── Exceções ──────────────────────────────────────────────────────────────────

class OpFError(Exception):
    """Base para erros da sessão OpF."""


class OpFTransientError(OpFError):
    """Erro temporário — deve ser retentado (5xx, timeout, 403 CloudFront)."""


class OpFFatalError(OpFError):
    """Erro fatal — não retentar (4xx não-auth, corpo inválido)."""


# ── Sessão ────────────────────────────────────────────────────────────────────

class OpFSession:
    """Sessão HTTP autenticada compartilhada contra o dashboard OpF.

    Mantém 1 browser + 1 context + 1 page. Todos os POSTs/GETs reutilizam o
    mesmo contexto, herdando cookies do CloudFront/Next.js.

    Não é thread-safe no sentido forte, mas o `refresh()` é protegido por
    lock para evitar concorrência de reautenticação.
    """

    def __init__(self, playwright, logger: logging.Logger | None = None):
        self._p = playwright
        self._log = logger or logging.getLogger(__name__)
        self._browser = None
        self._page = None
        self._refresh_lock = threading.Lock()
        self._bootstrap()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _bootstrap(self) -> None:
        """Abre browser + page e navega para BASE_URL para popular cookies."""
        self._browser = create_browser(self._p)
        self._page = create_page(self._browser)
        # goto_with_retry já lida com retry de 403 CloudFront.
        # Usa "body" como selector — qualquer HTML renderizado o contém.
        goto_with_retry(self._page, BASE_URL, "body", logger=self._log)
        self._log.debug("OpFSession: bootstrap concluído")

    def refresh(self) -> None:
        """Re-navega para BASE_URL para reobter cookies (após 401/403)."""
        with self._refresh_lock:
            self._log.info("OpFSession: refreshing session (re-navigating to BASE_URL)")
            try:
                self._page.context.clear_cookies()
            except Exception:
                pass
            goto_with_retry(self._page, BASE_URL, "body", logger=self._log)

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None
            self._page = None

    def __enter__(self) -> "OpFSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ── Request helpers ───────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{BASE_URL}{path}"

    def _parse_response(self, resp, path: str) -> Any:
        """Converte APIResponse em dict/list. Lança exceções classificadas."""
        status = resp.status

        if status in (401, 403):
            try:
                self.refresh()
            except Exception as e:
                raise OpFTransientError(
                    f"{path} returned {status} and refresh failed: {e}"
                ) from e
            raise OpFTransientError(
                f"{path} returned {status}; session refreshed — retry"
            )

        if 500 <= status < 600:
            body = _safe_text(resp)
            raise OpFTransientError(f"{path} returned {status}: {body[:200]}")

        if not resp.ok:
            body = _safe_text(resp)
            raise OpFFatalError(f"{path} returned {status}: {body[:200]}")

        try:
            return resp.json()
        except Exception as e:
            body = _safe_text(resp)
            raise OpFFatalError(
                f"{path} returned non-JSON body ({type(e).__name__}): {body[:200]}"
            ) from e

    def post(self, path: str, body: dict) -> Any:
        """POST JSON body; retorna dict/list parseado."""
        url = self._url(path)
        try:
            resp = self._page.request.post(
                url,
                data=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            raise OpFTransientError(
                f"POST {path} network error ({type(e).__name__}): {e}"
            ) from e
        return self._parse_response(resp, f"POST {path}")

    def get(self, path: str, params: dict | None = None) -> Any:
        """GET; retorna dict/list parseado."""
        url = self._url(path)
        try:
            resp = self._page.request.get(url, params=params or {})
        except Exception as e:
            raise OpFTransientError(
                f"GET {path} network error ({type(e).__name__}): {e}"
            ) from e
        return self._parse_response(resp, f"GET {path}")

    # ── Discovery de metadata (F2) ────────────────────────────────────────────

    def discover_apis_and_endpoints(
        self,
        cache_path: Path | str | None = None,
        cache_ttl: int = 24 * 60 * 60,
    ) -> dict | None:
        """Descobre APIs e endpoints navegando na página de api-requests e
        interceptando chamadas de metadata.

        Retorna dict no formato:
            {
                "apis": ["credit-cards-accounts", ...],
                "endpoints": {
                    "credit-cards-accounts": [{"id": 35, "label": "..."}, ...],
                    ...
                },
                "source": "live" | "cache",
                "fetched_at": ISO8601,
            }
        ou None se a descoberta falhar (caller deve usar fallback hardcoded).

        Cache em JSON no `cache_path`; se presente e dentro do TTL, devolve-o
        sem tocar na rede. Como o dashboard OpF está atrás de CloudFront e nem
        sempre devolve metadata estruturada via um único endpoint conhecido,
        capturamos QUALQUER resposta JSON trafegada durante o carregamento da
        página que contenha chaves `api`/`apis` + `endpoint`/`endpoints`, e
        tentamos reconciliar em {api: [endpoints]}.
        """
        # 1) Tenta cache fresco
        if cache_path:
            cached = _load_meta_cache(Path(cache_path), cache_ttl)
            if cached:
                self._log.info(
                    "OpFSession.discover: usando cache (%d APIs, %d endpoints)",
                    len(cached.get("apis", [])),
                    sum(len(v) for v in cached.get("endpoints", {}).values()),
                )
                cached["source"] = "cache"
                return cached

        # 2) Tenta descobrir via navegação
        try:
            live = self._discover_live()
        except Exception as e:
            self._log.warning(
                "OpFSession.discover: falha na descoberta ao vivo (%s): %s",
                type(e).__name__, e,
            )
            return None

        if not live:
            return None

        live["source"] = "live"
        live["fetched_at"] = _utc_now_iso()

        # 3) Persiste cache
        if cache_path:
            try:
                _save_meta_cache(Path(cache_path), live)
            except Exception as e:
                self._log.warning(
                    "OpFSession.discover: falha ao salvar cache em %s: %s",
                    cache_path, e,
                )

        self._log.info(
            "OpFSession.discover: discovery ao vivo (%d APIs, %d endpoints)",
            len(live.get("apis", [])),
            sum(len(v) for v in live.get("endpoints", {}).values()),
        )
        return live

    def _discover_live(self) -> dict | None:
        """Navega a página de api-requests e intercepta respostas de metadata.

        Varre respostas JSON durante o load da página procurando estruturas
        que se pareçam com listas de APIs/endpoints. Estratégia best-effort:
        - captura todas respostas que contenham 'api' ou 'endpoint' no path
        - tenta extrair (api_id, endpoint_id, label) de cada item
        - agrupa por api_id
        """
        page = self._page
        captured: list[tuple[str, Any]] = []

        def _on_response(resp):
            url_l = resp.url.lower()
            if ("/api/" not in url_l
                or "organisations" in url_l
                or "unique-consents" in url_l):
                return
            # Foca em endpoints que mencionem metadata/apis/endpoints
            if not any(k in url_l for k in ("endpoint", "api", "metadata", "catalog")):
                return
            try:
                data = resp.json()
            except Exception:
                return
            captured.append((resp.url, data))

        page.on("response", _on_response)
        try:
            page.goto(
                f"{BASE_URL}/transactional-data/api-requests/evolution",
                wait_until="networkidle",
                timeout=45000,
            )
            page.wait_for_timeout(1500)
        finally:
            page.remove_listener("response", _on_response)

        if not captured:
            return None

        endpoints_by_api: dict[str, dict[int, str]] = {}

        for _url, data in captured:
            _collect_endpoints_from(data, endpoints_by_api)

        if not endpoints_by_api:
            return None

        apis_sorted = sorted(endpoints_by_api.keys())
        endpoints_result: dict[str, list[dict]] = {}
        for api_id in apis_sorted:
            items = [
                {"id": ep_id, "label": label}
                for ep_id, label in sorted(endpoints_by_api[api_id].items())
            ]
            endpoints_result[api_id] = items

        return {
            "apis": apis_sorted,
            "endpoints": endpoints_result,
        }


# ── Utilitários ───────────────────────────────────────────────────────────────

def _safe_text(resp) -> str:
    try:
        return resp.text()
    except Exception:
        return "<no body>"


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _load_meta_cache(path: Path, ttl: int) -> dict | None:
    """Carrega cache de metadata se existir e estiver dentro do TTL."""
    try:
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > ttl:
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if "apis" not in data or "endpoints" not in data:
            return None
        return data
    except Exception:
        return None


def _save_meta_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _collect_endpoints_from(
    node: Any,
    acc: dict[str, dict[int, str]],
    api_hint: str | None = None,
) -> None:
    """Varre recursivamente uma estrutura JSON procurando registros que se
    pareçam com endpoints (com id numérico + label/name) e agrupa por api_id.

    Heurísticas:
    - Dict com 'api' + ('endpoints' | 'items' | 'list'): recursa usando api como hint
    - Dict com 'id' (int) + ('label'|'name'|'title') e api_hint conhecido:
      registra como endpoint desse api
    - List: recursa em cada item
    """
    if isinstance(node, dict):
        new_api = api_hint
        # Detecta dict que representa uma API
        for key in ("api", "api_id", "apiId", "apiName", "name"):
            val = node.get(key)
            if isinstance(val, str) and _looks_like_api_id(val):
                new_api = val
                break

        # Detecta endpoint dentro do dict atual
        endpoint_id = node.get("id")
        label = (
            node.get("label")
            or node.get("name")
            or node.get("title")
            or node.get("description")
            or ""
        )
        if (
            isinstance(endpoint_id, int)
            and isinstance(label, str)
            and label.strip()
            and new_api
            and _looks_like_api_id(new_api)
            and not _looks_like_api_id(label)  # evita auto-registrar a própria API
        ):
            acc.setdefault(new_api, {})[endpoint_id] = label.strip()

        for v in node.values():
            _collect_endpoints_from(v, acc, api_hint=new_api)

    elif isinstance(node, list):
        for item in node:
            _collect_endpoints_from(item, acc, api_hint=api_hint)


# Lista canônica conhecida de API IDs do Open Finance Brasil — usada como
# whitelist de discovery para filtrar ruído de outras chaves string.
_KNOWN_API_IDS = frozenset({
    "credit-cards-accounts", "consents", "accounts", "exchanges", "customers",
    "funds", "unarranged-accounts-overdraft", "invoice-financings", "loans",
    "financings", "resources", "bank-fixed-incomes", "credit-fixed-incomes",
    "variable-incomes", "treasure-titles",
})


def _looks_like_api_id(val: str) -> bool:
    if val in _KNOWN_API_IDS:
        return True
    # Heurística para novos ids ainda não catalogados: kebab-case, 2+ hifens
    # ou entre 6-40 chars sem espaço. Conservador para evitar falsos positivos.
    if not val or " " in val or "/" in val:
        return False
    return val.islower() and "-" in val and 6 <= len(val) <= 40
