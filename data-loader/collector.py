"""
collector.py — Pipeline de coleta + exportação CSV local
=========================================================
Orquestra:
  1. Coleta de consentimentos via scrapers.run_consents()
  2. Coleta de API requests via scrapers.run_api_requests()
  3. Exportação CSV com upsert em data/ (sem duplicatas)

Também define RunLogger: um logger por receptor + log global, um arquivo por execução.
"""

import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import config
import scrapers
from browser import fridays_between


# ─────────────────────────────────────────────────────────────────────────────
# RunLogger
# ─────────────────────────────────────────────────────────────────────────────

class RunLogger:
    """
    Gerencia um conjunto de log files para uma execução (run_id = YYYY-MM-DD_HH-MM-SS).
    - Um log global:       logs/_global/{run_id}.log
    - Um log por receptor: logs/{receptor_safe}/{run_id}.log
    """

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._loggers: dict[str, logging.Logger] = {}

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^\w\-]", "_", name)

    def _make_logger(self, name: str, log_path: Path) -> logging.Logger:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"opf.{self.run_id}.{name}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if not logger.handlers:
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)-8s %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
            )
            logger.addHandler(fh)

            sh = logging.StreamHandler()
            sh.setLevel(logging.INFO)
            sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s",
                                              datefmt="%H:%M:%S"))
            logger.addHandler(sh)

        return logger

    def global_(self) -> logging.Logger:
        """Logger global da execução (logs/_global/{run_id}.log)."""
        key = "_global"
        if key not in self._loggers:
            log_path = config.LOG_DIR / "_global" / f"{self.run_id}.log"
            self._loggers[key] = self._make_logger(key, log_path)
        return self._loggers[key]

    def get(self, receptor_name: str) -> logging.Logger:
        """Logger por receptor (logs/{receptor_safe}/{run_id}.log)."""
        key = self._safe_name(receptor_name)
        if key not in self._loggers:
            log_path = config.LOG_DIR / key / f"{self.run_id}.log"
            self._loggers[key] = self._make_logger(key, log_path)
        return self._loggers[key]


# ─────────────────────────────────────────────────────────────────────────────
# CSV upsert local
# ─────────────────────────────────────────────────────────────────────────────

def upsert_csv(
    existing: pd.DataFrame | None,
    new: pd.DataFrame,
    pk_cols: list[str],
) -> tuple[pd.DataFrame, int, int]:
    """
    Merge sem duplicata usando pk_cols como chave primária.
    Retorna (merged_df, n_new, n_updated).
    """
    if existing is None or existing.empty:
        return new.copy(), len(new), 0

    merged   = pd.concat([existing, new], ignore_index=True)
    merged   = merged.drop_duplicates(subset=pk_cols, keep="last")
    n_new    = max(0, len(merged) - len(existing))
    n_updated = len(new) - n_new
    return merged, n_new, max(0, n_updated)


def _sync_csv(db_query: str, db_path: Path, csv_path: Path,
              pk_cols: list[str], log: logging.Logger,
              params: tuple = ()) -> tuple[int, int]:
    """Lê SQLite, faz upsert com CSV local (se existir) e salva."""
    con = sqlite3.connect(str(db_path))
    new_df = pd.read_sql_query(db_query, con, params=params)
    con.close()

    existing = pd.read_csv(csv_path) if csv_path.exists() else None
    merged, n_new, n_upd = upsert_csv(existing, new_df, pk_cols)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(csv_path, index=False)
    log.info(
        f"{csv_path.name}: {n_new} novos + {n_upd} atualizados "
        f"({len(merged)} total) → {csv_path}"
    )
    return n_new, n_upd


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _persist_endpoint_history(
    db_path: Path,
    endpoints_map: dict,
    source: str,
    log: logging.Logger,
) -> None:
    """Grava snapshot do mapa {api: [endpoints]} em endpoint_history.

    Idempotente por (fetched_at, api, endpoint_id) — fetched_at é UTC ISO.
    Nunca quebra a coleta: erros apenas geram warning.
    """
    try:
        fetched_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for api_id, eps in (endpoints_map or {}).items():
            for ep in eps:
                rows.append((
                    fetched_at, api_id,
                    int(ep.get("id", 0)), str(ep.get("label", "")),
                    source,
                ))
        if not rows:
            return
        con = sqlite3.connect(str(db_path))
        try:
            con.executemany("""
                INSERT OR IGNORE INTO endpoint_history
                    (fetched_at, api, endpoint_id, endpoint_label, source)
                VALUES (?, ?, ?, ?, ?)
            """, rows)
            con.commit()
        finally:
            con.close()
        log.debug(
            f"endpoint_history: {len(rows)} registros gravados (source={source})"
        )
    except Exception as e:
        log.warning(f"endpoint_history: falha ao persistir snapshot: {e}")


def _filter_receptors(receptor_list: list[dict], names: list[str] | None) -> list[dict]:
    if not names:
        return receptor_list
    lower = [n.lower() for n in names]
    return [r for r in receptor_list if any(n in r["label"].lower() for n in lower)]


def _active_receptors(db_path: Path, dates: list[str]) -> list[dict]:
    start, end = dates[0][:10], dates[-1][:10]
    con = sqlite3.connect(str(db_path))
    rows = con.execute("""
        SELECT DISTINCT receptor, receptor_uuid
        FROM unique_consents
        WHERE total > 0 AND date BETWEEN ? AND ?
        ORDER BY receptor
    """, (start, end)).fetchall()
    con.close()
    return [{"label": r[0], "value": r[1]} for r in rows]


def _resolve_dates(start_date: str, end_date: str) -> list[str]:
    today = datetime.now(timezone.utc)

    if end_date in ("today", "hoje") or not end_date:
        end = today
    else:
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

    if start_date.endswith("w"):
        start = today - timedelta(weeks=int(start_date[:-1]))
    elif start_date.endswith("m"):
        start = today - timedelta(days=int(start_date[:-1]) * 30)
    else:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)

    return fridays_between(start, end)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def run_collection(
    start_date: str = "4w",
    end_date: str = "today",
    workers: int | None = None,
    delay_min: float = 3.0,
    delay_max: float = 8.0,
    receptor_filter: list[str] | None = None,
) -> dict:
    """
    Pipeline completo:
      1. Resolve datas → lista de sextas-feiras
      2. Coleta consentimentos → SQLite
      3. Busca receptores ativos
      4. Coleta API requests → SQLite
      5. Para cada CSV em data/: lê existente, faz upsert, salva

    Retorna dict com estatísticas da execução.
    """
    run_logger = RunLogger()
    log = run_logger.global_()
    run_id = run_logger.run_id
    _workers = workers if workers is not None else config.DEFAULT_WORKERS

    log.info(f"=== Execução iniciada: {run_id} ===")
    log.info(f"Período: {start_date} → {end_date} | workers={_workers}")
    t0 = time.time()

    # Garante que as tabelas de telemetria existam antes de start_run.
    from telemetry import start_run, finalize_run
    scrapers.open_db(config.DB_PATH).close()
    start_run(config.DB_PATH, run_id)

    # ── 1. Datas ───────────────────────────────────────────────────────────────
    dates = _resolve_dates(start_date, end_date)
    if not dates:
        log.error("Nenhuma sexta-feira encontrada no período.")
        return {"error": "Nenhuma sexta-feira no período", "run_id": run_id}
    log.info(f"Sextas-feiras: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)")

    # ── 2. Consentimentos ──────────────────────────────────────────────────────
    log.info("--- Fase 1a: Consentimentos únicos ---")
    n_consents = scrapers.run_consents(dates=dates, db_path=config.DB_PATH,
                                       workers=_workers, logger=log,
                                       delay_min=delay_min, delay_max=delay_max,
                                       run_id=run_id,
                                       receptor_filter=receptor_filter)

    # ── 2b. Consentimentos ativos (receptor × transmissor) ─────────────────────
    log.info("--- Fase 1b: Consentimentos ativos ---")
    ac_summary = scrapers.run_active_consents(
        dates=dates, db_path=config.DB_PATH,
        workers=_workers, logger=log,
        delay_min=delay_min, delay_max=delay_max,
        run_id=run_id,
        receptor_filter=receptor_filter,
    )
    log.info(
        f"Consentimentos ativos: ok={ac_summary['ok']} "
        f"failed={ac_summary['failed']} skipped={ac_summary['skipped']}"
    )

    # ── 3. Receptores ativos ───────────────────────────────────────────────────
    receptors = _active_receptors(config.DB_PATH, dates)
    receptors = _filter_receptors(receptors, receptor_filter)
    log.info(f"Receptores ativos: {len(receptors)}")

    # ── 4. API Requests ────────────────────────────────────────────────────────
    n_api = 0
    if receptors:
        # Busca lista de transmissores + discovery de APIs/endpoints antes da
        # coleta granular (uma única sessão reaproveitada para ambos).
        log.info("--- Fase 2: API Requests ---")
        log.info("Buscando lista de transmissores e metadata de APIs...")
        from playwright.sync_api import sync_playwright
        from session import OpFSession
        with sync_playwright() as _p:
            with OpFSession(_p, logger=log) as _session:
                transmitters = scrapers.fetch_transmitters(_session)
                meta = _session.discover_apis_and_endpoints(
                    cache_path=config.META_CACHE_PATH,
                    cache_ttl=config.META_CACHE_TTL,
                )
        log.info(f"Transmissores: {len(transmitters)}")

        # Decide entre metadata descoberto e fallback hardcoded.
        apis_arg = None
        endpoints_arg = None
        if meta:
            discovered_apis = meta.get("apis") or []
            discovered_eps = meta.get("endpoints") or {}
            total_eps = sum(len(v) for v in discovered_eps.values())
            # Piso mínimo: só usa discovery se estiver coerente com o que
            # sabemos do domínio. Caso contrário, mantém hardcoded.
            if len(discovered_apis) >= 10 and total_eps >= 50:
                apis_arg = discovered_apis
                endpoints_arg = discovered_eps
                log.info(
                    f"Discovery: usando {len(discovered_apis)} APIs e "
                    f"{total_eps} endpoints ({meta.get('source', 'live')})"
                )
                _persist_endpoint_history(
                    config.DB_PATH, discovered_eps,
                    source=meta.get("source", "live"), log=log,
                )
            else:
                log.warning(
                    f"Discovery: resultado abaixo do piso mínimo "
                    f"({len(discovered_apis)} APIs / {total_eps} endpoints) — "
                    f"caindo para fallback hardcoded."
                )
        else:
            log.info("Discovery: sem metadata, usando fallback hardcoded.")

        # Persiste também o fallback como snapshot, para rastreio de drift.
        if apis_arg is None:
            _persist_endpoint_history(
                config.DB_PATH, scrapers.ENDPOINTS, source="fallback", log=log,
            )

        n_api = scrapers.run_api_requests(dates=dates, receptors=receptors,
                                           db_path=config.DB_PATH,
                                           workers=_workers, logger=log,
                                           delay_min=delay_min, delay_max=delay_max,
                                           transmitters=transmitters,
                                           run_id=run_id,
                                           apis=apis_arg,
                                           endpoints_map=endpoints_arg)
    else:
        log.warning("Nenhum receptor ativo — fase 2 pulada.")

    # ── 5. Exportação CSV local ────────────────────────────────────────────────
    log.info("--- Exportação CSV local ---")
    start_d, end_d = dates[0][:10], dates[-1][:10]

    n_new_c, n_upd_c = _sync_csv(
        "SELECT * FROM unique_consents WHERE date BETWEEN ? AND ?",
        config.DB_PATH, config.DATA_DIR / "consents.csv",
        ["date", "receptor_uuid"], log, (start_d, end_d),
    )
    n_new_a, n_upd_a = _sync_csv(
        "SELECT * FROM api_requests WHERE date BETWEEN ? AND ?",
        config.DB_PATH, config.DATA_DIR / "api_requests.csv",
        ["date", "receptor_uuid", "transmitter_uuid", "api", "endpoint_id", "status"], log, (start_d, end_d),
    )
    n_new_ac, n_upd_ac = _sync_csv(
        "SELECT * FROM active_consents WHERE date BETWEEN ? AND ?",
        config.DB_PATH, config.DATA_DIR / "active_consents.csv",
        ["receptor_uuid", "transmitter_uuid", "date"], log, (start_d, end_d),
    )

    duration = round(time.time() - t0, 1)

    # Finaliza run_summary e loga resumo de saúde.
    summary = finalize_run(
        config.DB_PATH, run_id,
        total_upserted=(n_new_c + n_upd_c + n_new_ac + n_upd_ac + n_new_a + n_upd_a),
    )
    api_total = summary.get("phase_api_ok", 0) + summary.get("phase_api_failed", 0)
    api_fail_pct = (
        100 * summary.get("phase_api_failed", 0) / api_total
        if api_total > 0 else 0.0
    )
    log.info(
        f"Saúde da coleta: consents ok/fail = "
        f"{summary.get('phase_consents_ok', 0)}/{summary.get('phase_consents_failed', 0)} | "
        f"active_consents ok/fail = "
        f"{summary.get('phase_active_consents_ok', 0)}/{summary.get('phase_active_consents_failed', 0)} | "
        f"api ok/fail = {summary.get('phase_api_ok', 0)}/{summary.get('phase_api_failed', 0)} "
        f"({api_fail_pct:.1f}% falha)"
    )
    log.info(f"=== Concluído em {duration}s ===")

    # Mantém api_group_weekly em sincronia para o dashboard.
    log.info("Atualizando api_group_weekly...")
    _agw_con = sqlite3.connect(str(config.DB_PATH))
    try:
        scrapers.refresh_api_group_weekly(_agw_con)
    finally:
        _agw_con.close()
    log.info("api_group_weekly atualizado.")

    return {
        "run_id":                    run_id,
        "period":                    f"{start_d} → {end_d}",
        "weeks":                     len(dates),
        "receptors":                 len(receptors),
        "n_consents_db":             n_consents,
        "n_api_db":                  n_api,
        "n_new_consents":            n_new_c,
        "n_upd_consents":            n_upd_c,
        "n_new_active_consents":     n_new_ac,
        "n_upd_active_consents":     n_upd_ac,
        "n_new_api":                 n_new_a,
        "n_upd_api":                 n_upd_a,
        "duration_s":                duration,
        "active_consents_ok":        summary.get("phase_active_consents_ok", 0),
        "active_consents_failed":    summary.get("phase_active_consents_failed", 0),
        "api_ok":                    summary.get("phase_api_ok", 0),
        "api_failed":                summary.get("phase_api_failed", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline payment-initiation
# ─────────────────────────────────────────────────────────────────────────────

def run_payment_initiation_collection(
    start_date: str = "4w",
    end_date: str = "today",
    workers: int | None = None,
    delay_min: float = 3.0,
    delay_max: float = 8.0,
    receptor_filter: list[str] | None = None,
) -> dict:
    """Pipeline de coleta para payment-initiation (Iniciação de Pagamentos).

    Diferenças em relação a run_collection():
      - Sem fase de consentimentos (endpoint /api/unique-consents não é usado nessa phase)
      - APIs e endpoints descobertos dinamicamente via /api/apis e /api/endpoints
      - Receptores = iniciadoras (PISPs, role=client); transmissores = detentores
      - Persiste em payment_api_requests
    """
    run_logger = RunLogger()
    log = run_logger.global_()
    run_id = run_logger.run_id
    _workers = workers if workers is not None else config.DEFAULT_WORKERS

    log.info(f"=== Execução payment-initiation iniciada: {run_id} ===")
    log.info(f"Período: {start_date} → {end_date} | workers={_workers}")
    t0 = time.time()

    from telemetry import start_run, finalize_run
    scrapers.open_db(config.DB_PATH).close()
    start_run(config.DB_PATH, run_id)

    dates = _resolve_dates(start_date, end_date)
    if not dates:
        log.error("Nenhuma sexta-feira encontrada no período.")
        return {"error": "Nenhuma sexta-feira no período", "run_id": run_id}
    log.info(f"Sextas-feiras: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)")

    log.info("--- Descoberta de receptores, transmissores e metadata ---")
    from playwright.sync_api import sync_playwright
    from session import OpFSession
    with sync_playwright() as _p:
        with OpFSession(_p, logger=log) as _session:
            receptors_all, transmitters = scrapers.fetch_payment_orgs(_session)
            apis, endpoints_map = scrapers.fetch_apis_endpoints(
                _session, phase=scrapers.PHASE_PAYMENT_INITIATION,
            )

    receptors = _filter_receptors(receptors_all, receptor_filter)
    total_eps = sum(len(v) for v in endpoints_map.values())
    log.info(
        f"PI: {len(receptors_all)} PISPs (filtro: {len(receptors)}) · "
        f"{len(transmitters)} detentores · {len(apis)} APIs · {total_eps} endpoints"
    )

    if not receptors:
        log.warning("Nenhum receptor (PISP) selecionado — coleta abortada.")
        return {"error": "sem receptores", "run_id": run_id}

    if not apis or total_eps == 0:
        log.error(
            f"Discovery vazio (apis={len(apis)}, endpoints={total_eps}). "
            f"Sem fallback hardcoded para payment-initiation — abortando."
        )
        return {"error": "discovery vazio", "run_id": run_id}

    # Persiste snapshot de endpoints (source='live-pi') para rastreio de drift.
    _persist_endpoint_history(
        config.DB_PATH, endpoints_map, source="live-pi", log=log,
    )

    n_api = scrapers.run_api_requests(
        dates=dates, receptors=receptors, db_path=config.DB_PATH,
        workers=_workers, logger=log,
        delay_min=delay_min, delay_max=delay_max,
        transmitters=transmitters, run_id=run_id,
        apis=apis, endpoints_map=endpoints_map,
        phase=scrapers.PHASE_PAYMENT_INITIATION,
        target_table="payment_api_requests",
        target_prefix="pi:",
    )

    # Exportação CSV local (espelha api_requests.csv).
    log.info("--- Exportação CSV local ---")
    start_d, end_d = dates[0][:10], dates[-1][:10]
    n_new, n_upd = _sync_csv(
        "SELECT * FROM payment_api_requests WHERE date BETWEEN ? AND ?",
        config.DB_PATH, config.DATA_DIR / "payment_api_requests.csv",
        ["date", "receptor_uuid", "transmitter_uuid", "api", "endpoint_id", "status"],
        log, (start_d, end_d),
    )

    duration = round(time.time() - t0, 1)
    summary = finalize_run(config.DB_PATH, run_id, total_upserted=(n_new + n_upd))
    log.info(f"=== Concluído em {duration}s ===")

    return {
        "run_id":     run_id,
        "phase":      scrapers.PHASE_PAYMENT_INITIATION,
        "period":     f"{start_d} → {end_d}",
        "weeks":      len(dates),
        "receptors":  len(receptors),
        "apis":       len(apis),
        "endpoints":  total_eps,
        "n_api_db":   n_api,
        "n_new":      n_new,
        "n_upd":      n_upd,
        "duration_s": duration,
        "api_ok":     summary.get("phase_api_ok", 0),
        "api_failed": summary.get("phase_api_failed", 0),
    }
