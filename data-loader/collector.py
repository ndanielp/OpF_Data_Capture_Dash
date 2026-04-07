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
    _workers = workers if workers is not None else config.DEFAULT_WORKERS

    log.info(f"=== Execução iniciada: {run_logger.run_id} ===")
    log.info(f"Período: {start_date} → {end_date} | workers={_workers}")
    t0 = time.time()

    # ── 1. Datas ───────────────────────────────────────────────────────────────
    dates = _resolve_dates(start_date, end_date)
    if not dates:
        log.error("Nenhuma sexta-feira encontrada no período.")
        return {"error": "Nenhuma sexta-feira no período", "run_id": run_logger.run_id}
    log.info(f"Sextas-feiras: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)")

    # ── 2. Consentimentos ──────────────────────────────────────────────────────
    log.info("--- Fase 1: Consentimentos ---")
    n_consents = scrapers.run_consents(dates=dates, db_path=config.DB_PATH,
                                       workers=_workers, logger=log,
                                       delay_min=delay_min, delay_max=delay_max)

    # ── 3. Receptores ativos ───────────────────────────────────────────────────
    receptors = _active_receptors(config.DB_PATH, dates)
    log.info(f"Receptores ativos: {len(receptors)}")

    # ── 4. API Requests ────────────────────────────────────────────────────────
    n_api = 0
    if receptors:
        # Busca lista de transmissores antes da coleta granular
        log.info("--- Fase 2: API Requests ---")
        log.info("Buscando lista de transmissores...")
        from playwright.sync_api import sync_playwright
        from browser import create_browser, create_page
        with sync_playwright() as _p:
            _b = create_browser(_p)
            _pg = create_page(_b)
            transmitters = scrapers.fetch_transmitters(_pg)
            _b.close()
        log.info(f"Transmissores: {len(transmitters)}")

        n_api = scrapers.run_api_requests(dates=dates, receptors=receptors,
                                           db_path=config.DB_PATH,
                                           workers=_workers, logger=log,
                                           delay_min=delay_min, delay_max=delay_max,
                                           transmitters=transmitters)
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

    duration = round(time.time() - t0, 1)
    log.info(f"=== Concluído em {duration}s ===")

    return {
        "run_id":         run_logger.run_id,
        "period":         f"{start_d} → {end_d}",
        "weeks":          len(dates),
        "receptors":      len(receptors),
        "n_consents_db":  n_consents,
        "n_api_db":       n_api,
        "n_new_consents": n_new_c,
        "n_upd_consents": n_upd_c,
        "n_new_api":      n_new_a,
        "n_upd_api":      n_upd_a,
        "duration_s":     duration,
    }
