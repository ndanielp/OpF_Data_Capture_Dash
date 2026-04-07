"""
scrapers.py — Coleta de dados do Open Finance Brasil
=====================================================
Scraping de consentimentos únicos e chamadas de API por receptor.

Derivado de openfinance-poc/build_consents_db.py + build_api_requests_db.py.
Sem dependências Rich — usa logging Python padrão.
Workers recebem logger via queue de progresso; main process faz o logging.
"""

import copy
import json
import logging
import multiprocessing as mp
import random
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Route, sync_playwright

from browser import (
    BASE_URL,
    create_browser,
    create_page,
    goto_with_retry,
    parse_record_date,
)

# ── Constantes ─────────────────────────────────────────────────────────────────

_CONSENTS_PAGE_URL = f"{BASE_URL}/transactional-data/unique-consents/receivers"
_CONSENTS_API_URL  = f"{BASE_URL}/api/unique-consents"

_API_REQUESTS_PAGE_URL  = f"{BASE_URL}/transactional-data/api-requests/evolution"
_API_REQUESTS_ENDPOINT  = f"{BASE_URL}/api/api-requests"

APIS = [
    "credit-cards-accounts",
    "consents",
    "accounts",
    "exchanges",
    "customers",
    "funds",
    "unarranged-accounts-overdraft",
    "invoice-financings",
    "loans",
    "financings",
    "resources",
    "bank-fixed-incomes",
    "credit-fixed-incomes",
    "variable-incomes",
    "treasure-titles",
]

STATUSES = [200, 500]

_WORKER_COUNT   = 3
_WORKER_STAGGER = 4  # segundos entre o início de cada worker

_RECEPTOR_DROPDOWN = "[class*='-control']"
_RECEPTOR_OPTIONS  = "[class*='-option']"

_DROPDOWN_TIMEOUT = 4_000   # ms — timeout por tentativa de abrir o dropdown
_RESPONSE_TIMEOUT = 6_000   # ms — timeout para a resposta da API chegar


def _click_dropdown_option(page, click_idx: int, max_retries: int = 2) -> None:
    """Abre o dropdown de receptor e clica na opção click_idx.
    Se o dropdown não abrir (estado inconsistente pós-combo), pressiona Escape
    e retenta uma vez antes de propagar o erro.
    """
    for attempt in range(max_retries):
        try:
            page.locator(_RECEPTOR_DROPDOWN).first.click()
            page.wait_for_selector(_RECEPTOR_OPTIONS, state="visible", timeout=_DROPDOWN_TIMEOUT)
            page.locator(_RECEPTOR_OPTIONS).nth(click_idx).click()
            return
        except Exception:
            if attempt == max_retries - 1:
                raise
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)


# ── Banco de dados ─────────────────────────────────────────────────────────────

def open_db(path: Path) -> sqlite3.Connection:
    """Abre/cria banco SQLite com as duas tabelas de dados."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS unique_consents (
            date           TEXT NOT NULL,
            receptor       TEXT NOT NULL,
            receptor_uuid  TEXT NOT NULL,
            cpf            INTEGER NOT NULL DEFAULT 0,
            cnpj           INTEGER NOT NULL DEFAULT 0,
            total          INTEGER NOT NULL DEFAULT 0,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS api_requests (
            date           TEXT NOT NULL,
            receptor       TEXT NOT NULL,
            receptor_uuid  TEXT NOT NULL,
            api            TEXT NOT NULL,
            status         INTEGER NOT NULL,
            total          INTEGER NOT NULL DEFAULT 0,
            fetched_at     TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid, api, status)
        )
    """)
    con.commit()
    return con


def upsert_consents(con: sqlite3.Connection, records: list[dict], fetched_at: str) -> int:
    rows = [
        (r["date"], r["receptor"], r["receptor_uuid"],
         r["cpf"], r["cnpj"], r["total"], fetched_at)
        for r in records
    ]
    con.executemany("""
        INSERT OR REPLACE INTO unique_consents
            (date, receptor, receptor_uuid, cpf, cnpj, total, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    con.commit()
    return len(rows)


def upsert_api_requests(con: sqlite3.Connection, records: list[dict]) -> int:
    rows = [
        (r["date"], r["receptor"], r["receptor_uuid"],
         r["api"], r["status"], r["total"], r["fetched_at"])
        for r in records
    ]
    con.executemany("""
        INSERT OR REPLACE INTO api_requests
            (date, receptor, receptor_uuid, api, status, total, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    con.commit()
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# CONSENTIMENTOS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_orgs(page) -> list[dict]:
    """Navega para a página de consentimentos e captura a lista de receptores."""
    orgs: list[dict] = []

    def _capture(resp):
        if "/api/organisations" in resp.url:
            try:
                orgs.extend(resp.json())
            except Exception:
                pass

    page.on("response", _capture)
    page.goto(_CONSENTS_PAGE_URL, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(1000)
    return orgs


def fetch_consents_for_org(
    page, org_uuid: str, dates: list[str], click_idx: int = 0
) -> list[dict]:
    """
    Dispara POST /api/unique-consents via route interception + click no dropdown.
    Usa expect_response para aguardar a resposta (até 8s).
    """
    captured: list[dict] = []

    def route_handler(route: Route):
        try:
            body = json.loads(route.request.post_data or "{}")
            body["dates"] = dates
            body["orgs"]  = [org_uuid]
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    page.route(_CONSENTS_API_URL, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/unique-consents" in r.url, timeout=_RESPONSE_TIMEOUT
        ) as resp_info:
            _click_dropdown_option(page, click_idx)
        data = resp_info.value.json()
        if isinstance(data, list):
            captured.extend(data)
    except Exception:
        pass
    finally:
        page.unroute(_CONSENTS_API_URL, route_handler)

    return captured


def build_consent_records(raw: list[dict], org: dict) -> list[dict]:
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


def _worker_run_consents(
    worker_id: int, chunk: list[dict], dates: list[str], fetched_at: str, queue, delay_min: float, delay_max: float
) -> list[dict]:
    """
    Roda em processo separado: fetch via browser, sem escrita em disco.
    Envia progresso via queue. Retorna lista de registros coletados.
    """
    queue.put(("log", worker_id, f"W{worker_id}: {len(chunk)} receptores"))

    with sync_playwright() as p:
        queue.put(("ready", worker_id, len(chunk)))
        browser = create_browser(p)

        for i, org in enumerate(chunk, 1):
            t0 = time.time()
            page = create_page(browser)
            goto_with_retry(page, _CONSENTS_PAGE_URL, "[class*='-control']")
            queue.put(("start", worker_id, org["label"], i))

            raw     = fetch_consents_for_org(page, org["value"], dates, click_idx=0)
            records = build_consent_records(raw, org)
            nonzero = sum(1 for r in records if r["total"] > 0)
            queue.put(("org_done", worker_id, org["label"], len(records), nonzero, records))

            page.context.close()
            elapsed = time.time() - t0
            queue.put(("timing", worker_id, org["label"], elapsed))
            time.sleep(random.uniform(delay_min, delay_max))

        browser.close()

    queue.put(("done", worker_id))
    return []


def run_consents(
    dates: list[str], db_path: str | Path, workers: int = _WORKER_COUNT, logger=None, delay_min: float = 3.0, delay_max: float = 8.0
) -> int:
    """
    Coleta consentimentos únicos para todos os receptores e persiste em SQLite.
    Retorna total de registros inseridos/atualizados.
    """
    log = logger or logging.getLogger(__name__)
    fetched_at = datetime.now(timezone.utc).isoformat()
    db_path = Path(db_path)

    log.info("Consentimentos: carregando lista de receptores...")
    with sync_playwright() as p:
        browser = create_browser(p)
        page = create_page(browser)
        goto_with_retry(page, _CONSENTS_PAGE_URL, "[class*='-control']", logger=log)
        orgs = fetch_orgs(page)
        browser.close()

    log.info(f"Consentimentos: {len(orgs)} receptores encontrados")
    if not orgs:
        return 0

    today_str = fetched_at[:10]
    try:
        con = sqlite3.connect(str(db_path))
        rows = con.execute(
            "SELECT DISTINCT receptor_uuid FROM unique_consents WHERE fetched_at LIKE ?", 
            (f"{today_str}%",)
        ).fetchall()
        con.close()
        fetched_uuids = {r[0] for r in rows}
    except Exception:
        fetched_uuids = set()

    orgs_to_fetch = [org for org in orgs if org["value"] not in fetched_uuids]
    
    if len(fetched_uuids) > 0:
        log.info(f"Consentimentos: {len(fetched_uuids)} receptores já consultados hoje. Restam {len(orgs_to_fetch)}.")

    if not orgs_to_fetch:
        return 0

    log.info(
        f"Consentimentos: período {dates[0][:10]} → {dates[-1][:10]} "
        f"({len(dates)} semanas · {len(orgs_to_fetch)} receptores · {workers} workers)"
    )

    n = min(workers, len(orgs_to_fetch))
    chunks = [orgs_to_fetch[i::n] for i in range(n)]

    con = open_db(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    total_upserted = 0

    with mp.Manager() as mgr:
        queue = mgr.Queue()
        with ProcessPoolExecutor(max_workers=n) as executor:
            futures = {
                executor.submit(_worker_run_consents, i + 1, chunk, dates, fetched_at, queue, delay_min, delay_max): i + 1
                for i, chunk in enumerate(chunks) if chunk
            }
            completed: set[int] = set()

            while len(completed) < len(futures):
                while not queue.empty():
                    msg = queue.get_nowait()
                    _handle_queue_msg(msg, log, "Consentimentos")
                    if msg[0] == "org_done" and len(msg) > 5 and msg[5]:
                        total_upserted += upsert_consents(con, msg[5], fetched_at)

                for future, wid in list(futures.items()):
                    if future.done() and wid not in completed:
                        completed.add(wid)
                        try:
                            future.result()
                        except Exception as exc:
                            log.error(f"Consentimentos W{wid} falhou: {exc}")

                time.sleep(0.15)

            while not queue.empty():
                msg = queue.get_nowait()
                _handle_queue_msg(msg, log, "Consentimentos")
                if msg[0] == "org_done" and len(msg) > 5 and msg[5]:
                    total_upserted += upsert_consents(con, msg[5], fetched_at)

    con.close()

    log.info(f"Consentimentos: {total_upserted} registros inseridos/atualizados no SQLite")
    return total_upserted


# ─────────────────────────────────────────────────────────────────────────────
# API REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

def probe_receptor(page, receptor_uuid: str, dates: list[str]) -> bool:
    """
    Verifica se receptor tem qualquer chamada no período (qualquer status).
    Retorna True se há dados, False se vazio. Em caso de erro retorna True.
    """
    body = {
        "axis":      "date",
        "phase":     "transactional-data",
        "receivers": [receptor_uuid],
        "dates":     dates,
    }

    def route_handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body))
        except Exception:
            route.continue_()

    page.route(_API_REQUESTS_ENDPOINT, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/api-requests" in r.url, timeout=_RESPONSE_TIMEOUT
        ) as resp_info:
            _click_dropdown_option(page, 0)
        data = resp_info.value.json()
        return isinstance(data, list) and any(d.get("total", 0) > 0 for d in data)
    except Exception:
        return True
    finally:
        page.unroute(_API_REQUESTS_ENDPOINT, route_handler)


def fetch_api_combo(
    page, receptor_uuid: str, api_id: str, status: int, dates: list[str], click_idx: int
) -> list[dict]:
    """
    Dispara POST /api/api-requests para uma combinação (receptor, api, status)
    via route interception + click no dropdown.
    """
    captured: list[dict] = []

    body_override = {
        "axis":      "date",
        "phase":     "transactional-data",
        "apis":      [api_id],
        "receivers": [receptor_uuid],
        "dates":     dates,
        "status":    status,
    }

    def route_handler(route: Route):
        try:
            route.continue_(post_data=json.dumps(body_override))
        except Exception:
            route.continue_()

    _log = logging.getLogger(__name__)
    page.route(_API_REQUESTS_ENDPOINT, route_handler)
    try:
        with page.expect_response(
            lambda r: "/api/api-requests" in r.url, timeout=_RESPONSE_TIMEOUT
        ) as resp_info:
            _click_dropdown_option(page, click_idx)
        data = resp_info.value.json()
        if isinstance(data, list):
            captured.extend(data)
            if not captured:
                _log.debug(
                    "fetch_api_combo: resposta vazia (lista vazia) para "
                    "api=%s status=%s receptor=%s", api_id, status, receptor_uuid
                )
        else:
            _log.warning(
                "fetch_api_combo: resposta inesperada (nao-lista) para "
                "api=%s status=%s receptor=%s — tipo=%s",
                api_id, status, receptor_uuid, type(data).__name__
            )
    except Exception as exc:
        _log.warning(
            "fetch_api_combo FALHOU: api=%s status=%s receptor=%s — %s: %s",
            api_id, status, receptor_uuid, type(exc).__name__, exc
        )
    finally:
        page.unroute(_API_REQUESTS_ENDPOINT, route_handler)

    return captured


def build_api_records(
    raw: list[dict], receptor: dict, api_id: str, status: int, fetched_at: str
) -> list[dict]:
    records = []
    for item in raw:
        raw_date = str(item.get("date") or item.get("_id") or "")
        if not raw_date:
            continue
        records.append({
            "date":          parse_record_date(raw_date),
            "receptor":      receptor["label"],
            "receptor_uuid": receptor["value"],
            "api":           api_id,
            "status":        status,
            "total":         item.get("total", 0),
            "fetched_at":    fetched_at,
        })
    return records


def _worker_run_api_requests(
    worker_id: int, chunk: list[dict], dates: list[str], fetched_at: str, queue, delay_min: float, delay_max: float
) -> list[dict]:
    """
    Roda em processo separado: fetch via browser, sem escrita em disco.
    Envia progresso via queue. Retorna lista de registros coletados.
    """

    time.sleep((worker_id - 1) * _WORKER_STAGGER)
    queue.put(("log", worker_id, f"W{worker_id}: {len(chunk)} receptores"))

    with sync_playwright() as p:
        queue.put(("ready", worker_id, len(chunk)))
        browser = create_browser(p)

        for i, receptor in enumerate(chunk, 1):
            t0 = time.time()
            page = create_page(browser)
            goto_with_retry(page, _API_REQUESTS_PAGE_URL, _RECEPTOR_DROPDOWN)
            queue.put(("start", worker_id, receptor["label"], i))

            has_data = probe_receptor(page, receptor["value"], dates)
            if not has_data:
                queue.put(("skipped", worker_id, receptor["label"]))
                page.context.close()
                elapsed = time.time() - t0
                queue.put(("timing", worker_id, receptor["label"], elapsed))
                time.sleep(random.uniform(delay_min, delay_max))
                continue

            call_count = 1
            for api_id in APIS:
                for status in STATUSES:
                    click_idx = call_count % 2
                    call_count += 1
                    raw = fetch_api_combo(
                        page, receptor["value"], api_id, status, dates, click_idx
                    )
                    records = build_api_records(raw, receptor, api_id, status, fetched_at)
                    nonzero = sum(1 for r in records if r["total"] > 0)
                    queue.put(("combo", worker_id, api_id, status, nonzero, records))

            page.context.close()
            elapsed = time.time() - t0
            queue.put(("timing", worker_id, receptor["label"], elapsed))
            time.sleep(random.uniform(delay_min, delay_max))

        browser.close()

    queue.put(("done", worker_id))
    return []


def run_api_requests(
    dates: list[str],
    receptors: list[dict],
    db_path: str | Path,
    workers: int = _WORKER_COUNT,
    logger=None,
    delay_min: float = 3.0,
    delay_max: float = 8.0,
) -> int:
    """
    Coleta chamadas de API por receptor × API × status e persiste em SQLite.
    receptors: lista de {"label": str, "value": uuid}
    Retorna total de registros inseridos/atualizados.
    """
    log = logger or logging.getLogger(__name__)
    fetched_at = datetime.now(timezone.utc).isoformat()
    db_path = Path(db_path)

    log.info(
        f"API Requests: {len(receptors)} receptores · {len(APIS)} APIs · "
        f"{len(STATUSES)} statuses · {workers} workers"
    )

    n = min(workers, len(receptors))
    chunks = [receptors[i::n] for i in range(n)]

    con = open_db(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    total_upserted = 0

    with mp.Manager() as mgr:
        queue = mgr.Queue()
        with ProcessPoolExecutor(max_workers=n) as executor:
            futures = {
                executor.submit(
                    _worker_run_api_requests, i + 1, chunk, dates, fetched_at, queue, delay_min, delay_max
                ): i + 1
                for i, chunk in enumerate(chunks) if chunk
            }
            completed: set[int] = set()

            while len(completed) < len(futures):
                while not queue.empty():
                    msg = queue.get_nowait()
                    _handle_queue_msg(msg, log, "API Requests")
                    if msg[0] == "combo" and len(msg) > 5 and msg[5]:
                        total_upserted += upsert_api_requests(con, msg[5])

                for future, wid in list(futures.items()):
                    if future.done() and wid not in completed:
                        completed.add(wid)
                        try:
                            future.result()
                        except Exception as exc:
                            log.error(f"API Requests W{wid} falhou: {exc}")

                time.sleep(0.15)

            while not queue.empty():
                msg = queue.get_nowait()
                _handle_queue_msg(msg, log, "API Requests")
                if msg[0] == "combo" and len(msg) > 5 and msg[5]:
                    total_upserted += upsert_api_requests(con, msg[5])

    con.close()

    log.info(f"API Requests: {total_upserted} registros inseridos/atualizados no SQLite")
    return total_upserted


# ── Queue logging helper ───────────────────────────────────────────────────────

def _handle_queue_msg(msg: tuple, log: logging.Logger, prefix: str) -> None:
    """Converte mensagens da queue de progresso dos workers em log entries."""
    kind = msg[0]
    wid  = msg[1]
    if kind == "log":
        log.debug(f"{prefix} W{wid}: {msg[2]}")
    elif kind == "ready":
        log.info(f"{prefix} W{wid}: iniciado ({msg[2]} receptores)")
    elif kind == "start":
        log.info(f"{prefix} W{wid}: coletando '{msg[2]}' ({msg[3]})")
    elif kind == "org_done":
        log.info(
            f"{prefix} W{wid}: '{msg[2]}' concluído — "
            f"{msg[3]} registros ({msg[4]} não-zero)"
        )
    elif kind == "skipped":
        log.info(f"{prefix} W{wid}: '{msg[2]}' sem dados, pulado")
    elif kind == "combo":
        if msg[4] > 0:
            log.debug(f"{prefix} W{wid}: {msg[2]} status={msg[3]} → {msg[4]} registros")
    elif kind == "timing":
        log.debug(f"{prefix} W{wid}: '{msg[2]}' — {msg[3]:.1f}s")
    elif kind == "done":
        log.info(f"{prefix} W{wid}: concluído")
