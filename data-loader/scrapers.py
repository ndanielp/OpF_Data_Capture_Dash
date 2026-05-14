"""
scrapers.py — Coleta de dados do Open Finance Brasil
=====================================================
Scraping de consentimentos únicos e chamadas de API por receptor × transmissor × endpoint.

Derivado de openfinance-poc/build_consents_db.py + build_api_requests_db.py.
Sem dependências Rich — usa logging Python padrão.
Workers recebem logger via queue de progresso; main process faz o logging.
"""

import logging
import multiprocessing as mp
import random
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from browser import BASE_URL, parse_record_date
from session import OpFError, OpFSession, OpFTransientError


# Política de retry para chamadas HTTP ao dashboard OpF:
# - 3 tentativas com backoff exponencial (1s, 3s, 8s)
# - Retenta apenas OpFTransientError (5xx, timeout, 401/403 pós-refresh)
# - OpFFatalError aborta imediatamente sem retry
# - reraise=True: propaga a última exceção em vez de embrulhar em RetryError
_RETRY_POLICY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(OpFTransientError),
    reraise=True,
)

# ── Constantes ─────────────────────────────────────────────────────────────────

_CONSENTS_PAGE_URL = f"{BASE_URL}/transactional-data/unique-consents/receivers"
_CONSENTS_API_URL  = f"{BASE_URL}/api/unique-consents"

_API_REQUESTS_PAGE_URL  = f"{BASE_URL}/transactional-data/api-requests/evolution"
_API_REQUESTS_ENDPOINT  = f"{BASE_URL}/api/api-requests"

# Página de payment-initiation: dispara /api/organisations (client + server)
# e /api/apis + /api/endpoints com phase="payment-initiation".
_PI_API_REQUESTS_PAGE_URL = f"{BASE_URL}/payment-initiation/api-requests/evolution"

# Phases conhecidas do dashboard OpF. Usadas em probe/fetch e discovery.
PHASE_TRANSACTIONAL = "transactional-data"
PHASE_PAYMENT_INITIATION = "payment-initiation"

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

# Mapeamento de endpoints por API: cada entrada é {"label": str, "id": int}
# IDs extraídos via interceptação de POST body em 2026-04-07.
ENDPOINTS: dict[str, list[dict]] = {
    "credit-cards-accounts": [
        {"label": "Fatura de Cartão de Crédito", "id": 35},
        {"label": "Identificação de cartão de crédito", "id": 31},
        {"label": "Limites de cartão de crédito", "id": 32},
        {"label": "Lista de cartões de crédito", "id": 30},
        {"label": "Transações de cartão de crédito", "id": 33},
        {"label": "Transações de cartão de crédito por fatura", "id": 36},
        {"label": "Transações recentes de cartão de crédito", "id": 34},
    ],
    "consents": [
        {"label": "Criar novo pedido de consentimento", "id": 21},
        {"label": "Deletar / Revogar o consentimento identificado por consentId", "id": 80},
        {"label": "Obter detalhes de extensões feitas no consentimento", "id": 111},
        {"label": "Obter detalhes do consentimento identificado por consentId", "id": 22},
        {"label": "Renovar consentimento", "id": 112},
    ],
    "accounts": [
        {"label": "Identificação da Conta", "id": 38},
        {"label": "Limites da Conta", "id": 42},
        {"label": "Lista de Contas", "id": 37},
        {"label": "Saldos da Conta", "id": 39},
        {"label": "Transações da Conta", "id": 40},
        {"label": "Transações recentes da Conta", "id": 41},
    ],
    "exchanges": [
        {"label": "Eventos", "id": 110},
        {"label": "Identificação do produto", "id": 109},
        {"label": "Lista de produtos", "id": 108},
    ],
    "customers": [
        {"label": "Identificação pessoa jurídica", "id": 25},
        {"label": "Identificação pessoa natural", "id": 24},
        {"label": "Qualificação pessoa jurídica", "id": 27},
        {"label": "Qualificação pessoa natural", "id": 26},
        {"label": "Relacionamento pessoa jurídica", "id": 29},
        {"label": "Relacionamento pessoa natural", "id": 28},
    ],
    "funds": [
        {"label": "Identificação do Investimento", "id": 104},
        {"label": "Lista de Investimentos", "id": 103},
        {"label": "Saldos", "id": 105},
        {"label": "Transações", "id": 106},
        {"label": "Transações recentes", "id": 107},
    ],
    "unarranged-accounts-overdraft": [
        {"label": "Adiantamento a Depositantes", "id": 53},
        {"label": "Contrato", "id": 54},
        {"label": "Garantias do Contrato", "id": 55},
        {"label": "Pagamentos do Contrato", "id": 56},
        {"label": "Parcelas do Contrato", "id": 57},
    ],
    "invoice-financings": [
        {"label": "Garantias do Contrato", "id": 60},
        {"label": "Identificação do Contrato", "id": 59},
        {"label": "Lista de Contratos", "id": 58},
        {"label": "Pagamentos do Contrato", "id": 61},
        {"label": "Parcelas do Contrato", "id": 62},
    ],
    "loans": [
        {"label": "Empréstimos", "id": 43},
        {"label": "Garantias do Contrato", "id": 45},
        {"label": "Identificação do Contrato", "id": 44},
        {"label": "Pagamentos do Contrato", "id": 46},
        {"label": "Parcelas do Contrato", "id": 47},
    ],
    "financings": [
        {"label": "Garantias do Contrato", "id": 50},
        {"label": "Identificação do Contrato", "id": 49},
        {"label": "Lista de financiamentos", "id": 48},
        {"label": "Pagamentos do Contrato", "id": 51},
        {"label": "Parcelas do Contrato", "id": 52},
    ],
    "resources": [
        {"label": "Obtém a lista de recursos consentidos pelo cliente", "id": 23},
    ],
    "bank-fixed-incomes": [
        {"label": "Identificação do Investimento", "id": 88},
        {"label": "Lista de Investimentos", "id": 87},
        {"label": "Saldos", "id": 89},
        {"label": "Transações", "id": 90},
        {"label": "Transações recentes", "id": 91},
    ],
    "credit-fixed-incomes": [
        {"label": "Identificação do Investimento", "id": 83},
        {"label": "Lista de Investimentos", "id": 82},
        {"label": "Saldos", "id": 84},
        {"label": "Transações", "id": 85},
        {"label": "Transações recentes", "id": 86},
    ],
    "variable-incomes": [
        {"label": "Detalhes da nota de negociação", "id": 97},
        {"label": "Identificação do Investimento", "id": 93},
        {"label": "Lista de Investimentos", "id": 92},
        {"label": "Saldos", "id": 94},
        {"label": "Transações", "id": 95},
        {"label": "Transações recentes", "id": 96},
    ],
    "treasure-titles": [
        {"label": "Identificação do Investimento", "id": 99},
        {"label": "Lista de Investimentos", "id": 98},
        {"label": "Saldos", "id": 100},
        {"label": "Transações", "id": 101},
        {"label": "Transações recentes", "id": 102},
    ],
}

_WORKER_COUNT   = 3
_WORKER_STAGGER = 4  # segundos entre o início de cada worker


# ── Banco de dados ─────────────────────────────────────────────────────────────

def open_db(path: Path) -> sqlite3.Connection:
    """Abre/cria banco SQLite com as tabelas de dados e migra schema se necessário."""
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

    # Cria tabela api_requests com schema completo (nova instalação)
    con.execute("""
        CREATE TABLE IF NOT EXISTS api_requests (
            date              TEXT NOT NULL,
            receptor          TEXT NOT NULL,
            receptor_uuid     TEXT NOT NULL,
            transmitter       TEXT NOT NULL DEFAULT '',
            transmitter_uuid  TEXT NOT NULL DEFAULT '',
            api               TEXT NOT NULL,
            endpoint          TEXT NOT NULL DEFAULT '',
            endpoint_id       INTEGER NOT NULL DEFAULT 0,
            status            INTEGER NOT NULL,
            total             INTEGER NOT NULL DEFAULT 0,
            fetched_at        TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid, transmitter_uuid, api, endpoint_id, status)
        )
    """)

    # Migração idempotente: adiciona colunas ausentes em bancos antigos
    existing_cols = {row[1] for row in con.execute("PRAGMA table_info(api_requests)").fetchall()}
    migrations = [
        ("transmitter",      "TEXT NOT NULL DEFAULT ''"),
        ("transmitter_uuid", "TEXT NOT NULL DEFAULT ''"),
        ("endpoint",         "TEXT NOT NULL DEFAULT ''"),
        ("endpoint_id",      "INTEGER NOT NULL DEFAULT 0"),
    ]
    for col, definition in migrations:
        if col not in existing_cols:
            con.execute(f"ALTER TABLE api_requests ADD COLUMN {col} {definition}")

    # Recria tabela se a PRIMARY KEY não inclui transmitter_uuid/endpoint_id
    # (detectado pela ausência de 'transmitter_uuid' nas colunas da PK)
    pk_cols = {
        row[1] for row in con.execute("PRAGMA table_info(api_requests)").fetchall()
        if row[5] > 0  # pk position > 0 means part of PK
    }
    if "transmitter_uuid" not in pk_cols or "endpoint_id" not in pk_cols:
        con.executescript("""
            BEGIN;
            CREATE TABLE IF NOT EXISTS api_requests_new (
                date              TEXT NOT NULL,
                receptor          TEXT NOT NULL,
                receptor_uuid     TEXT NOT NULL,
                transmitter       TEXT NOT NULL DEFAULT '',
                transmitter_uuid  TEXT NOT NULL DEFAULT '',
                api               TEXT NOT NULL,
                endpoint          TEXT NOT NULL DEFAULT '',
                endpoint_id       INTEGER NOT NULL DEFAULT 0,
                status            INTEGER NOT NULL,
                total             INTEGER NOT NULL DEFAULT 0,
                fetched_at        TEXT NOT NULL,
                PRIMARY KEY (date, receptor_uuid, transmitter_uuid, api, endpoint_id, status)
            );
            INSERT OR IGNORE INTO api_requests_new
                (date, receptor, receptor_uuid, transmitter, transmitter_uuid,
                 api, endpoint, endpoint_id, status, total, fetched_at)
            SELECT date, receptor, receptor_uuid,
                   COALESCE(transmitter, ''), COALESCE(transmitter_uuid, ''),
                   api,
                   COALESCE(endpoint, ''), COALESCE(endpoint_id, 0),
                   status, total, fetched_at
            FROM api_requests;
            DROP TABLE api_requests;
            ALTER TABLE api_requests_new RENAME TO api_requests;
            COMMIT;
        """)

    # Tabelas de telemetria (F3).
    from telemetry import ensure_tables
    ensure_tables(con)

    # Snapshot diário de metadata (F2): permite detectar drift de IDs.
    con.execute("""
        CREATE TABLE IF NOT EXISTS endpoint_history (
            fetched_at     TEXT NOT NULL,
            api            TEXT NOT NULL,
            endpoint_id    INTEGER NOT NULL,
            endpoint_label TEXT NOT NULL DEFAULT '',
            source         TEXT NOT NULL DEFAULT 'fallback',
            PRIMARY KEY (fetched_at, api, endpoint_id)
        )
    """)

    # Payment-initiation: mesma forma de api_requests, tabela separada para
    # isolar semântica (PISP × detentor × api × endpoint × status). Sem
    # migrações incrementais — schema é estável desde criação.
    con.execute("""
        CREATE TABLE IF NOT EXISTS payment_api_requests (
            date              TEXT NOT NULL,
            receptor          TEXT NOT NULL,
            receptor_uuid     TEXT NOT NULL,
            transmitter       TEXT NOT NULL DEFAULT '',
            transmitter_uuid  TEXT NOT NULL DEFAULT '',
            api               TEXT NOT NULL,
            endpoint          TEXT NOT NULL DEFAULT '',
            endpoint_id       INTEGER NOT NULL DEFAULT 0,
            status            INTEGER NOT NULL,
            total             INTEGER NOT NULL DEFAULT 0,
            fetched_at        TEXT NOT NULL,
            PRIMARY KEY (date, receptor_uuid, transmitter_uuid, api, endpoint_id, status)
        )
    """)

    # Pré-agregação semanal por grupo de API — alimenta Mapa Estratégico e Evolução Temporal.
    con.execute("""
        CREATE TABLE IF NOT EXISTS api_group_weekly (
            date           TEXT    NOT NULL,
            receptor_uuid  TEXT    NOT NULL,
            receptor       TEXT    NOT NULL DEFAULT '',
            grp            TEXT    NOT NULL,
            req_week       INTEGER NOT NULL DEFAULT 0,
            consents_total INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, receptor_uuid, grp)
        )
    """)

    # Índices de leitura para o dashboard — criados uma vez, idempotentes.
    con.executescript("""
        CREATE INDEX IF NOT EXISTS idx_consents_date
            ON unique_consents(date);

        -- Covering index: SQLite resolve o GROUP BY do dashboard inteiramente
        -- pelo índice, sem ler as linhas da tabela principal (index-only scan).
        -- Inclui todas as colunas necessárias pela query de api_requests_dash.
        CREATE INDEX IF NOT EXISTS idx_api_dash_covering
            ON api_requests(date, receptor, api, endpoint_id, status, endpoint, total)
            WHERE endpoint_id <> 0;

        -- Índices para queries do Perfil Receptor (filtra por receptor_uuid, não receptor texto)
        CREATE INDEX IF NOT EXISTS idx_api_by_receptor
            ON api_requests(receptor_uuid, date, api, status, total);

        CREATE INDEX IF NOT EXISTS idx_consents_by_receptor
            ON unique_consents(receptor_uuid, date, total);

        CREATE INDEX IF NOT EXISTS idx_api_by_transmitter
            ON api_requests(transmitter_uuid, date, status, total);

        -- Índices para api_group_weekly
        CREATE INDEX IF NOT EXISTS idx_agw_receptor ON api_group_weekly(receptor_uuid, date);
        CREATE INDEX IF NOT EXISTS idx_agw_date     ON api_group_weekly(date);

        -- Índices para payment_api_requests (espelha api_requests).
        CREATE INDEX IF NOT EXISTS idx_pi_api_by_receptor
            ON payment_api_requests(receptor_uuid, date, api, status, total);
        CREATE INDEX IF NOT EXISTS idx_pi_api_by_transmitter
            ON payment_api_requests(transmitter_uuid, date, status, total);
        CREATE INDEX IF NOT EXISTS idx_pi_api_dash_covering
            ON payment_api_requests(date, receptor, api, endpoint_id, status, endpoint, total)
            WHERE endpoint_id <> 0;
    """)

    con.commit()
    return con


def refresh_api_group_weekly(con: sqlite3.Connection) -> None:
    """Recalcula api_group_weekly inteiramente a partir de api_requests x unique_consents.

    Deve ser chamado após cada run de coleta para manter a tabela em sincronia.
    executescript() auto-comita, portanto não requer commit() adicional.
    """
    con.executescript("""
        DELETE FROM api_group_weekly;
        INSERT INTO api_group_weekly (date, receptor_uuid, receptor, grp, req_week, consents_total)
        SELECT r.date, r.receptor_uuid, r.receptor,
               CASE
                   WHEN r.api = 'accounts'                                              THEN 'Conta'
                   WHEN r.api = 'credit-cards-accounts'                                 THEN 'Cartao'
                   WHEN r.api IN ('bank-fixed-incomes','credit-fixed-incomes',
                                  'variable-incomes','funds','treasure-titles')          THEN 'Investimento'
                   WHEN r.api IN ('loans','financings','invoice-financings',
                                  'unarranged-accounts-overdraft')                       THEN 'Credito'
                   WHEN r.api = 'exchanges'                                             THEN 'Cambio'
                   WHEN r.api = 'customers'                                             THEN 'Identidade'
                   WHEN r.api = 'resources'                                             THEN 'Resource'
               END AS grp,
               SUM(r.total)  AS req_week,
               c.total       AS consents_total
        FROM api_requests r
        JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
        WHERE r.api <> 'consents'
          AND r.status = 200
        GROUP BY r.date, r.receptor_uuid, grp
        HAVING grp IS NOT NULL;
    """)


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


def _upsert_records_into(
    con: sqlite3.Connection, table: str, records: list[dict],
) -> int:
    """Upsert genérico em tabelas com schema de api_requests
    (api_requests, payment_api_requests). Whitelist de nomes para evitar
    injeção via parâmetro `table`."""
    if table not in ("api_requests", "payment_api_requests"):
        raise ValueError(f"tabela não permitida em upsert: {table}")
    rows = [
        (r["date"], r["receptor"], r["receptor_uuid"],
         r["transmitter"], r["transmitter_uuid"],
         r["api"], r["endpoint"], r["endpoint_id"],
         r["status"], r["total"], r["fetched_at"])
        for r in records
    ]
    con.executemany(f"""
        INSERT OR REPLACE INTO {table}
            (date, receptor, receptor_uuid, transmitter, transmitter_uuid,
             api, endpoint, endpoint_id, status, total, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    con.commit()
    return len(rows)


def upsert_api_requests(con: sqlite3.Connection, records: list[dict]) -> int:
    return _upsert_records_into(con, "api_requests", records)


def upsert_payment_api_requests(con: sqlite3.Connection, records: list[dict]) -> int:
    return _upsert_records_into(con, "payment_api_requests", records)


# ─────────────────────────────────────────────────────────────────────────────
# CONSENTIMENTOS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_orgs(session: OpFSession) -> list[dict]:
    """Captura a lista de receptores via navegação na página de consentimentos.

    Navega na page interna da OpFSession e intercepta `/api/organisations`.
    Usamos navegação (em vez de HTTP direto) porque o front-end é quem determina
    quais query params distinguem receptores de transmissores, e replicar isso
    sem acesso ao DevTools seria especulação frágil. Como a chamada ocorre
    apenas 1x por execução, não há impacto no gargalo de performance.

    Retorna lista de {"label": str, "value": uuid}. Deduplica por uuid.
    """
    page = session._page
    orgs_by_uuid: dict[str, dict] = {}

    def _capture(resp):
        if "/api/organisations" in resp.url:
            try:
                data = resp.json()
            except Exception:
                return
            if isinstance(data, list):
                for item in data:
                    uuid = item.get("value")
                    if uuid and uuid not in orgs_by_uuid:
                        orgs_by_uuid[uuid] = item

    page.on("response", _capture)
    try:
        page.goto(_CONSENTS_PAGE_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1000)
    finally:
        page.remove_listener("response", _capture)

    return list(orgs_by_uuid.values())


@_RETRY_POLICY
def fetch_consents_for_org(
    session: OpFSession, org_uuid: str, dates: list[str]
) -> list[dict]:
    """POST /api/unique-consents direto via OpFSession, com retry em erros
    transientes (até 3 tentativas, backoff 1s/3s/8s).

    Propaga OpFTransientError (após 3 tentativas) ou OpFFatalError
    (imediato). Caller classifica como 'failed' em telemetria.
    """
    data = session.post("/api/unique-consents", {
        "dates": dates,
        "orgs":  [org_uuid],
        "role":  "client",
    })
    if isinstance(data, list):
        return data
    return []


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
    worker_id: int, chunk: list[dict], dates: list[str], fetched_at: str, queue,
    delay_min: float, delay_max: float, db_path: str, run_id: str,
) -> list[dict]:
    """
    Roda em processo separado: abre 1 OpFSession reutilizável e faz POST
    /api/unique-consents por receptor. Envia progresso via queue e
    registra cada tentativa em fetch_attempts (F3).
    """
    from telemetry import consents_target, log_attempt

    date_first, date_last = dates[0][:10], dates[-1][:10]
    queue.put(("log", worker_id, f"W{worker_id}: {len(chunk)} receptores"))

    with sync_playwright() as p:
        queue.put(("ready", worker_id, len(chunk)))
        with OpFSession(p) as session:
            for i, org in enumerate(chunk, 1):
                t0 = time.time()
                started_iso = datetime.now(timezone.utc).isoformat()
                target = consents_target(org["value"], date_first, date_last)
                queue.put(("start", worker_id, org["label"], i))

                records: list[dict] = []
                status_label = "ok"
                err_class = None
                err_msg = None
                try:
                    raw = fetch_consents_for_org(session, org["value"], dates)
                    records = build_consent_records(raw, org)
                    if not records:
                        status_label = "empty"
                except OpFError as exc:
                    status_label = "failed"
                    err_class = type(exc).__name__
                    err_msg = str(exc)[:500]
                    queue.put(("log", worker_id,
                               f"consents FALHOU para '{org['label']}': "
                               f"{err_class}: {exc}"))

                duration_ms = int((time.time() - t0) * 1000)
                log_attempt(
                    db_path, run_id, "consents", target,
                    started_iso, duration_ms, status_label,
                    error_class=err_class, error_msg=err_msg,
                    records_count=len(records),
                )

                nonzero = sum(1 for r in records if r["total"] > 0)
                queue.put(("org_done", worker_id, org["label"], len(records), nonzero, records))

                queue.put(("timing", worker_id, org["label"], duration_ms / 1000.0))
                time.sleep(random.uniform(delay_min, delay_max))

    queue.put(("done", worker_id))
    return []


def run_consents(
    dates: list[str], db_path: str | Path, workers: int = _WORKER_COUNT,
    logger=None, delay_min: float = 3.0, delay_max: float = 8.0,
    run_id: str = "",
    receptor_filter: list[str] | None = None,
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
        with OpFSession(p, logger=log) as session:
            orgs = fetch_orgs(session)

    if receptor_filter:
        lower = [n.lower() for n in receptor_filter]
        orgs = [o for o in orgs if any(n in o["label"].lower() for n in lower)]

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
                executor.submit(
                    _worker_run_consents, i + 1, chunk, dates, fetched_at,
                    queue, delay_min, delay_max, str(db_path), run_id,
                ): i + 1
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

def fetch_transmitters(
    session: OpFSession, page_url: str = _API_REQUESTS_PAGE_URL,
) -> list[dict]:
    """Captura a lista de transmissores navegando na página de api-requests.

    Intercepta `/api/organisations` via page.on("response"). A página chama
    o endpoint 2x — primeira captura = receptores, segunda = transmissores.

    Igual a fetch_orgs, evitamos especular sobre o endpoint real e
    mantemos a navegação única por execução.
    """
    page = session._page
    captured: list[list] = []

    def _on_response(resp):
        if "/api/organisations" in resp.url:
            try:
                data = resp.json()
            except Exception:
                return
            if isinstance(data, list):
                captured.append(data)

    page.on("response", _on_response)
    try:
        page.goto(page_url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
    finally:
        page.remove_listener("response", _on_response)

    # A segunda captura costuma ser a lista de transmissores.
    if len(captured) >= 2:
        return captured[1]
    elif len(captured) == 1:
        return captured[0]
    return []


def fetch_payment_orgs(session: OpFSession) -> tuple[list[dict], list[dict]]:
    """Captura receptores (PISPs) e transmissores (detentores) navegando
    na página de payment-initiation/api-requests/evolution.

    Diferente de transactional-data, aqui as duas chamadas a /api/organisations
    têm role distinto no body (`client` = PISP, `server` = detentor).
    Como as duas requests são disparadas em paralelo pelo front, a ordem das
    respostas é não determinística — pareamos cada resposta com o role do body
    da request associada para classificar corretamente.

    Retorna (PISPs, detentores) como listas de {"label", "value"}.
    """
    import json as _json
    page = session._page
    receptors: list[dict] = []
    transmitters: list[dict] = []

    def _on_response(resp):
        nonlocal receptors, transmitters
        if "/api/organisations" not in resp.url:
            return
        try:
            data = resp.json()
        except Exception:
            return
        if not isinstance(data, list):
            return
        role = ""
        try:
            body = resp.request.post_data
            if body:
                role = (_json.loads(body) or {}).get("role", "")
        except Exception:
            pass
        if role == "client":
            receptors = data
        elif role == "server":
            transmitters = data

    page.on("response", _on_response)
    try:
        page.goto(_PI_API_REQUESTS_PAGE_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
    finally:
        page.remove_listener("response", _on_response)

    return receptors, transmitters


def fetch_apis_endpoints(
    session: OpFSession, phase: str,
) -> tuple[list[str], dict[str, list[dict]]]:
    """Descobre APIs e endpoints de uma phase via POST /api/apis e /api/endpoints.

    A resposta de /api/endpoints traz o campo `group`, que casa com o `label` /
    `name` de /api/apis. Mapeamos `endpoint.group → api._id` para agrupar.

    Retorna (apis, endpoints_map) onde:
      apis = ["payments", "automatic-payments", "enrollments"]
      endpoints_map = {"payments": [{"id": 64, "label": "..."}, ...], ...}
    """
    apis_raw = session.post("/api/apis", {"phase": phase}) or []
    eps_raw  = session.post("/api/endpoints", {"phase": phase}) or []

    apis: list[str] = []
    label_to_id: dict[str, str] = {}
    for a in apis_raw:
        api_id = a.get("_id") or a.get("value")
        if not api_id:
            continue
        apis.append(api_id)
        for k in ("label", "name"):
            v = a.get(k)
            if isinstance(v, str) and v.strip():
                label_to_id[v.strip()] = api_id

    endpoints_map: dict[str, list[dict]] = {a: [] for a in apis}
    for ep in eps_raw:
        ep_id = ep.get("_id") if isinstance(ep.get("_id"), int) else ep.get("value")
        label = ep.get("label") or ep.get("name") or ""
        group = (ep.get("group") or "").strip()
        api_id = label_to_id.get(group)
        if not api_id or ep_id is None:
            continue
        endpoints_map.setdefault(api_id, []).append(
            {"id": int(ep_id), "label": str(label)}
        )

    for api_id in endpoints_map:
        endpoints_map[api_id].sort(key=lambda e: e["id"])

    return apis, endpoints_map


@_RETRY_POLICY
def _probe_post(session: OpFSession, body: dict) -> object:
    return session.post("/api/api-requests", body)


def probe_receptor(
    session: OpFSession, receptor_uuid: str, dates: list[str],
    phase: str = PHASE_TRANSACTIONAL,
) -> bool:
    """POST /api/api-requests sem filtros para verificar se o receptor tem
    chamadas no período.

    Retorna True se há dados, False se vazio. Em caso de erro transiente,
    retorna True (conservador — prefere coletar e descobrir vazio a pular).
    """
    body = {
        "axis":      "date",
        "phase":     phase,
        "receivers": [receptor_uuid],
        "dates":     dates,
    }
    try:
        data = _probe_post(session, body)
    except OpFError:
        return True  # conservador
    return isinstance(data, list) and any(d.get("total", 0) > 0 for d in data)


def probe_transmitter(
    session: OpFSession, receptor_uuid: str, transmitter_uuid: str, dates: list[str],
    phase: str = PHASE_TRANSACTIONAL,
) -> bool:
    """Probe L1: receptor + transmitter, sem api/endpoint/status.
    Retorna True se tem dados, False se vazio. Conservador em erros."""
    body = {
        "axis":         "date",
        "phase":        phase,
        "receivers":    [receptor_uuid],
        "transmitters": [transmitter_uuid],
        "dates":        dates,
    }
    try:
        data = _probe_post(session, body)
    except OpFError:
        return True
    return isinstance(data, list) and any(d.get("total", 0) > 0 for d in data)


def probe_api(
    session: OpFSession, receptor_uuid: str, transmitter_uuid: str,
    api_id: str, dates: list[str],
    phase: str = PHASE_TRANSACTIONAL,
) -> bool:
    """Probe L2: receptor + transmitter + api, sem endpoint/status.
    Retorna True se tem dados, False se vazio. Conservador em erros."""
    body = {
        "axis":         "date",
        "phase":        phase,
        "receivers":    [receptor_uuid],
        "transmitters": [transmitter_uuid],
        "apis":         [api_id],
        "dates":        dates,
    }
    try:
        data = _probe_post(session, body)
    except OpFError:
        return True
    return isinstance(data, list) and any(d.get("total", 0) > 0 for d in data)


@_RETRY_POLICY
def fetch_api_combo(
    session: OpFSession,
    receptor_uuid: str,
    api_id: str,
    status: int,
    dates: list[str],
    transmitter_uuid: str = "",
    endpoint_id: int = 0,
    phase: str = PHASE_TRANSACTIONAL,
) -> list[dict]:
    """POST /api/api-requests para uma combinação
    (receptor, transmissor, api, endpoint, status) via OpFSession,
    com retry em erros transientes (até 3 tentativas, backoff 1s/3s/8s).

    Propaga OpFTransientError (após 3 tentativas) ou OpFFatalError.
    """
    body: dict = {
        "axis":      "date",
        "phase":     phase,
        "apis":      [api_id],
        "receivers": [receptor_uuid],
        "dates":     dates,
        "status":    status,
    }
    if transmitter_uuid:
        body["transmitters"] = [transmitter_uuid]
    if endpoint_id:
        body["endpoints"] = [endpoint_id]

    data = session.post("/api/api-requests", body)
    if isinstance(data, list):
        return data
    # Response não-lista é tratada como resposta vazia — não é erro fatal
    # mas merece registro (ficará em fetch_attempts com status=empty em F3).
    logging.getLogger(__name__).warning(
        "fetch_api_combo: resposta não-lista para api=%s status=%s receptor=%s",
        api_id, status, receptor_uuid,
    )
    return []


def build_api_records(
    raw: list[dict],
    receptor: dict,
    api_id: str,
    status: int,
    fetched_at: str,
    transmitter: dict | None = None,
    endpoint: dict | None = None,
) -> list[dict]:
    t_label = transmitter["label"] if transmitter else ""
    t_uuid  = transmitter["value"] if transmitter else ""
    ep_label = endpoint["label"] if endpoint else ""
    ep_id    = endpoint["id"]    if endpoint else 0

    records = []
    for item in raw:
        raw_date = str(item.get("date") or item.get("_id") or "")
        if not raw_date:
            continue
        records.append({
            "date":             parse_record_date(raw_date),
            "receptor":         receptor["label"],
            "receptor_uuid":    receptor["value"],
            "transmitter":      t_label,
            "transmitter_uuid": t_uuid,
            "api":              api_id,
            "endpoint":         ep_label,
            "endpoint_id":      ep_id,
            "status":           status,
            "total":            item.get("total", 0),
            "fetched_at":       fetched_at,
        })
    return records


def _worker_run_api_requests(
    worker_id: int,
    chunk: list[dict],
    dates: list[str],
    fetched_at: str,
    queue,
    delay_min: float,
    delay_max: float,
    transmitters: list[dict],
    db_path: str,
    run_id: str,
    apis: list[str],
    endpoints_map: dict[str, list[dict]],
    phase: str = PHASE_TRANSACTIONAL,
    target_prefix: str = "",
) -> list[dict]:
    """
    Roda em processo separado: abre 1 OpFSession e itera combinações
    receptor × transmissor × api × endpoint × status via POST direto.
    Cada combo é checkpointed em fetch_attempts (skip se já ok/empty hoje)
    e registra seu resultado (ok/empty/failed) ao final.
    """
    from telemetry import (
        already_done, api_target, log_attempt,
        probe_transmitter_target, probe_api_target,
    )

    date_first, date_last = dates[0][:10], dates[-1][:10]

    time.sleep((worker_id - 1) * _WORKER_STAGGER)
    queue.put(("log", worker_id, f"W{worker_id}: {len(chunk)} receptores"))

    with sync_playwright() as p:
        queue.put(("ready", worker_id, len(chunk)))
        with OpFSession(p) as session:
            for i, receptor in enumerate(chunk, 1):
                t0 = time.time()
                queue.put(("start", worker_id, receptor["label"], i))

                has_data = probe_receptor(session, receptor["value"], dates, phase=phase)
                if not has_data:
                    queue.put(("skipped", worker_id, receptor["label"]))
                    elapsed = time.time() - t0
                    queue.put(("timing", worker_id, receptor["label"], elapsed))
                    time.sleep(random.uniform(delay_min, delay_max))
                    continue

                # transmitters=[] significa "sem filtro de transmissor" → usa sentinela None
                transmitter_iter = transmitters if transmitters else [None]

                for transmitter in transmitter_iter:
                    t_uuid  = transmitter["value"] if transmitter else None
                    t_label = transmitter["label"] if transmitter else ""

                    # ── L1: probe receptor + transmitter ──────────────────────
                    if t_uuid:
                        p_started = datetime.now(timezone.utc).isoformat()
                        p_t0 = time.time()
                        has_t = probe_transmitter(
                            session, receptor["value"], t_uuid, dates, phase=phase,
                        )
                        p_ms = int((time.time() - p_t0) * 1000)
                        if not has_t:
                            log_attempt(
                                db_path, run_id, "api_requests",
                                target_prefix + probe_transmitter_target(
                                    receptor["value"], t_uuid, date_first, date_last
                                ),
                                p_started, p_ms, "skipped",
                            )
                            queue.put(("skipped_transmitter", worker_id, t_label))
                            continue

                    for api_id in apis:
                        # ── L2: probe receptor + transmitter + api ─────────────
                        if t_uuid:
                            p_started = datetime.now(timezone.utc).isoformat()
                            p_t0 = time.time()
                            has_a = probe_api(
                                session, receptor["value"], t_uuid, api_id, dates,
                                phase=phase,
                            )
                            p_ms = int((time.time() - p_t0) * 1000)
                            if not has_a:
                                log_attempt(
                                    db_path, run_id, "api_requests",
                                    target_prefix + probe_api_target(
                                        api_id, receptor["value"], t_uuid,
                                        date_first, date_last
                                    ),
                                    p_started, p_ms, "skipped",
                                )
                                queue.put(("skipped_api", worker_id, api_id, t_label))
                                continue

                        ep_list = endpoints_map.get(api_id, [])
                        # Inclui sempre a opção "sem filtro de endpoint" (endpoint_id=0)
                        endpoints_iter = [None] + ep_list

                        for endpoint in endpoints_iter:
                            for status in STATUSES:
                                ep_id  = endpoint["id"] if endpoint else 0
                                t_uuid_str = t_uuid or ""
                                target = target_prefix + api_target(
                                    api_id, ep_id, status,
                                    receptor["value"], t_uuid_str,
                                    date_first, date_last,
                                )

                                # Checkpoint: pula se já coletado hoje com sucesso.
                                if already_done(db_path, target, run_id=None):
                                    continue

                                combo_t0 = time.time()
                                started_iso = datetime.now(timezone.utc).isoformat()

                                raw: list[dict] = []
                                status_label = "ok"
                                err_class = None
                                err_msg = None
                                try:
                                    raw = fetch_api_combo(
                                        session,
                                        receptor["value"],
                                        api_id,
                                        status,
                                        dates,
                                        transmitter_uuid=t_uuid_str,
                                        endpoint_id=ep_id,
                                        phase=phase,
                                    )
                                    if not raw:
                                        status_label = "empty"
                                except OpFError as exc:
                                    status_label = "failed"
                                    err_class = type(exc).__name__
                                    err_msg = str(exc)[:500]
                                    queue.put(("log", worker_id,
                                               f"combo FALHOU api={api_id} status={status} "
                                               f"endpoint_id={ep_id}: {err_class}: {exc}"))

                                records = build_api_records(
                                    raw, receptor, api_id, status, fetched_at,
                                    transmitter=transmitter,
                                    endpoint=endpoint,
                                )
                                combo_duration_ms = int((time.time() - combo_t0) * 1000)
                                log_attempt(
                                    db_path, run_id, "api_requests", target,
                                    started_iso, combo_duration_ms, status_label,
                                    error_class=err_class, error_msg=err_msg,
                                    records_count=len(records),
                                )

                                nonzero = sum(1 for r in records if r["total"] > 0)
                                queue.put(("combo", worker_id, api_id, status, nonzero, records))

                elapsed = time.time() - t0
                queue.put(("timing", worker_id, receptor["label"], elapsed))
                time.sleep(random.uniform(delay_min, delay_max))

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
    transmitters: list[dict] | None = None,
    run_id: str = "",
    apis: list[str] | None = None,
    endpoints_map: dict[str, list[dict]] | None = None,
    phase: str = PHASE_TRANSACTIONAL,
    target_table: str = "api_requests",
    target_prefix: str = "",
) -> int:
    """
    Coleta chamadas de API por receptor × transmissor × api × endpoint × status.
    Persiste em SQLite e retorna total de registros inseridos/atualizados.

    transmitters: lista de {"label": str, "value": uuid}.
                  Se None ou [], coleta sem filtro de transmissor.
    apis/endpoints_map: se None, usa fallback hardcoded APIS/ENDPOINTS.
                       Caller pode passar valores de discovery dinâmico (F2).
    phase: "transactional-data" (default) ou "payment-initiation".
    target_table: nome da tabela onde gravar os registros.
                  "api_requests" (default) ou "payment_api_requests".
    target_prefix: prefixo aplicado aos targets de telemetria, para que
                   checkpointing em fetch_attempts seja isolado por phase.
    """
    log = logger or logging.getLogger(__name__)
    fetched_at = datetime.now(timezone.utc).isoformat()
    db_path = Path(db_path)
    transmitters = transmitters or []
    apis = apis if apis else APIS
    endpoints_map = endpoints_map if endpoints_map else ENDPOINTS

    total_eps = sum(len(endpoints_map.get(a, [])) + 1 for a in apis)
    log.info(
        f"API Requests [{phase}]: {len(receptors)} receptores · "
        f"{len(transmitters)} transmissores · {len(apis)} APIs · "
        f"~{total_eps} endpoints · {len(STATUSES)} statuses · {workers} workers"
    )

    n = min(workers, len(receptors))
    chunks = [receptors[i::n] for i in range(n)]

    con = open_db(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    total_upserted = 0

    def _upsert(records: list[dict]) -> int:
        return _upsert_records_into(con, target_table, records)

    with mp.Manager() as mgr:
        queue = mgr.Queue()
        with ProcessPoolExecutor(max_workers=n) as executor:
            futures = {
                executor.submit(
                    _worker_run_api_requests,
                    i + 1, chunk, dates, fetched_at, queue, delay_min, delay_max,
                    transmitters, str(db_path), run_id,
                    apis, endpoints_map,
                    phase, target_prefix,
                ): i + 1
                for i, chunk in enumerate(chunks) if chunk
            }
            completed: set[int] = set()

            while len(completed) < len(futures):
                while not queue.empty():
                    msg = queue.get_nowait()
                    _handle_queue_msg(msg, log, "API Requests")
                    if msg[0] == "combo" and len(msg) > 5 and msg[5]:
                        total_upserted += _upsert(msg[5])

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
                    total_upserted += _upsert(msg[5])

    con.close()

    log.info(f"API Requests [{phase}]: {total_upserted} registros inseridos/atualizados no SQLite")
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
    elif kind == "skipped_transmitter":
        log.debug(f"{prefix} W{wid}: transmissor '{msg[2]}' sem dados — pulado (L1)")
    elif kind == "skipped_api":
        log.debug(f"{prefix} W{wid}: api '{msg[2]}' sem dados para '{msg[3]}' — pulada (L2)")
    elif kind == "combo":
        if msg[4] > 0:
            log.debug(f"{prefix} W{wid}: {msg[2]} status={msg[3]} → {msg[4]} registros")
    elif kind == "timing":
        log.debug(f"{prefix} W{wid}: '{msg[2]}' — {msg[3]:.1f}s")
    elif kind == "done":
        log.info(f"{prefix} W{wid}: concluído")
