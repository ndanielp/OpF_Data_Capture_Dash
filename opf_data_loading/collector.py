"""
collector.py — Pipeline de coleta + exportação CSV + Drive
===========================================================
Orquestra:
  1. Coleta de consentimentos via scrapers.run_consents()
  2. Coleta de API requests via scrapers.run_api_requests()
  3. Exportação CSV com upsert (sem duplicatas) para o Google Drive
  4. Upload de logs por receptor para o Drive

Também define RunLogger: um logger por receptor + log global, um arquivo por execução.
"""

import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import config
import drive as drv
import scrapers
from browser import fridays_between


# ─────────────────────────────────────────────────────────────────────────────
# RunLogger
# ─────────────────────────────────────────────────────────────────────────────

class RunLogger:
    """
    Gerencia um conjunto de log files para uma execução (run_id = YYYY-MM-DD_HH-MM-SS).
    - Um log global:      logs/_global/{run_id}.log
    - Um log por receptor: logs/{receptor_safe}/{run_id}.log
    """

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._loggers: dict[str, logging.Logger] = {}
        self._log_files: list[Path] = []

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

        self._log_files.append(log_path)
        return logger

    def global_(self) -> logging.Logger:
        """Logger global da execução (logs/_global/{run_id}.log)."""
        key = "_global"
        if key not in self._loggers:
            log_path = config.LOCAL_LOG_DIR / "_global" / f"{self.run_id}.log"
            self._loggers[key] = self._make_logger(key, log_path)
        return self._loggers[key]

    def get(self, receptor_name: str) -> logging.Logger:
        """Logger por receptor (logs/{receptor_safe}/{run_id}.log)."""
        key = self._safe_name(receptor_name)
        if key not in self._loggers:
            log_path = config.LOCAL_LOG_DIR / key / f"{self.run_id}.log"
            self._loggers[key] = self._make_logger(key, log_path)
        return self._loggers[key]

    def upload_all(self, service, root_folder_id: str) -> None:
        """Envia todos os arquivos de log desta execução para o Drive."""
        log = self.global_()
        for log_path in self._log_files:
            # Garante que todos os handlers foram flushed
            for handler in logging.getLogger(f"opf.{self.run_id}.{log_path.parent.name}").handlers:
                handler.flush()
            try:
                # Estrutura no Drive: logs/{pasta_pai}/{arquivo}
                folder_name = log_path.parent.name  # "_global" ou receptor_safe
                logs_root = drv.ensure_subfolder(service, root_folder_id, "logs")
                receptor_folder = drv.ensure_subfolder(service, logs_root, folder_name)
                drv.upload_local_file(service, receptor_folder, log_path)
                log.debug(f"Log enviado para Drive: {folder_name}/{log_path.name}")
            except Exception as exc:
                log.warning(f"Falha ao enviar log '{log_path}' para Drive: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# CSV upsert
# ─────────────────────────────────────────────────────────────────────────────

def upsert_csv(
    existing: pd.DataFrame | None,
    new: pd.DataFrame,
    pk_cols: list[str],
) -> tuple[pd.DataFrame, int, int]:
    """
    Merge sem duplicata usando as colunas pk_cols como chave primária.
    Retorna (merged_df, n_new, n_updated).
    """
    if existing is None or existing.empty:
        return new.copy(), len(new), 0

    # Identifica linhas novas e atualizadas
    merged = pd.concat([existing, new], ignore_index=True)
    # Mantém a última ocorrência por PK (new sobrescreve existing)
    merged = merged.drop_duplicates(subset=pk_cols, keep="last")

    n_before = len(existing)
    n_after  = len(merged)
    n_new     = max(0, n_after - n_before)
    n_updated = len(new) - n_new

    return merged, n_new, max(0, n_updated)


# ─────────────────────────────────────────────────────────────────────────────
# Leitura do SQLite
# ─────────────────────────────────────────────────────────────────────────────

def _read_consents(db_path: Path, dates: list[str]) -> pd.DataFrame:
    start, end = dates[0][:10], dates[-1][:10]
    con = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT * FROM unique_consents WHERE date BETWEEN ? AND ?",
        con, params=(start, end)
    )
    con.close()
    return df


def _read_api_requests(db_path: Path, dates: list[str]) -> pd.DataFrame:
    start, end = dates[0][:10], dates[-1][:10]
    con = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT * FROM api_requests WHERE date BETWEEN ? AND ?",
        con, params=(start, end)
    )
    con.close()
    return df


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


# ─────────────────────────────────────────────────────────────────────────────
# Resolução de datas
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_dates(start_date: str, end_date: str) -> list[str]:
    """Converte strings de período em lista de sextas-feiras ISO."""
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
) -> dict:
    """
    Pipeline completo:
      1. Resolve datas → lista de sextas-feiras
      2. Coleta consentimentos → SQLite
      3. Busca receptores ativos
      4. Coleta API requests → SQLite
      5. Para cada CSV: baixa do Drive, upsert, faz upload
      6. Faz upload dos logs para Drive

    Retorna dict com estatísticas da execução.
    """
    run_logger = RunLogger()
    log = run_logger.global_()

    _workers = workers if workers is not None else config.DEFAULT_WORKERS

    log.info(f"=== Execução iniciada: {run_logger.run_id} ===")
    log.info(f"Período: {start_date} → {end_date} | workers={_workers}")

    import time
    t0 = time.time()

    # ── 1. Resolver datas ──────────────────────────────────────────────────────
    dates = _resolve_dates(start_date, end_date)
    if not dates:
        log.error("Nenhuma sexta-feira encontrada no período informado.")
        return {"error": "Nenhuma sexta-feira no período", "run_id": run_logger.run_id}

    log.info(f"Sextas-feiras: {dates[0][:10]} → {dates[-1][:10]} ({len(dates)} semanas)")

    # ── 2. Coleta consentimentos ───────────────────────────────────────────────
    log.info("--- Fase 1: Consentimentos ---")
    n_consents = scrapers.run_consents(
        dates=dates,
        db_path=config.DB_PATH,
        workers=_workers,
        logger=log,
    )

    # ── 3. Receptores ativos ───────────────────────────────────────────────────
    receptors = _active_receptors(config.DB_PATH, dates)
    log.info(f"Receptores ativos no período: {len(receptors)}")

    # ── 4. Coleta API requests ─────────────────────────────────────────────────
    n_api = 0
    if receptors:
        log.info("--- Fase 2: API Requests ---")
        n_api = scrapers.run_api_requests(
            dates=dates,
            receptors=receptors,
            db_path=config.DB_PATH,
            workers=_workers,
            logger=log,
        )
    else:
        log.warning("Nenhum receptor ativo — fase 2 pulada.")

    # ── 5. Exportação CSV + Drive ──────────────────────────────────────────────
    n_new_consents = n_upd_consents = 0
    n_new_api = n_upd_api = 0

    if config.DRIVE_FOLDER_ID:
        log.info("--- Exportação CSV → Google Drive ---")
        try:
            service = drv.get_service(config.SERVICE_ACCOUNT_FILE)

            # Consentimentos
            new_consents_df  = _read_consents(config.DB_PATH, dates)
            existing_consents = drv.download_csv(service, config.DRIVE_FOLDER_ID, "consents.csv")
            merged_consents, n_new_consents, n_upd_consents = upsert_csv(
                existing_consents, new_consents_df, ["date", "receptor_uuid"]
            )
            drv.upload_csv(service, config.DRIVE_FOLDER_ID, "consents.csv", merged_consents)
            log.info(
                f"consents.csv: {n_new_consents} novos + {n_upd_consents} atualizados "
                f"({len(merged_consents)} total)"
            )

            # API Requests
            new_api_df  = _read_api_requests(config.DB_PATH, dates)
            existing_api = drv.download_csv(service, config.DRIVE_FOLDER_ID, "api_requests.csv")
            merged_api, n_new_api, n_upd_api = upsert_csv(
                existing_api, new_api_df, ["date", "receptor_uuid", "api", "status"]
            )
            drv.upload_csv(service, config.DRIVE_FOLDER_ID, "api_requests.csv", merged_api)
            log.info(
                f"api_requests.csv: {n_new_api} novos + {n_upd_api} atualizados "
                f"({len(merged_api)} total)"
            )

        except Exception as exc:
            log.error(f"Falha na exportação para Drive: {exc}")
    else:
        log.warning("DRIVE_FOLDER_ID não configurado — exportação para Drive ignorada.")

    # ── 6. Upload de logs ──────────────────────────────────────────────────────
    duration = round(time.time() - t0, 1)
    log.info(f"=== Execução concluída em {duration}s ===")

    if config.DRIVE_FOLDER_ID:
        try:
            service = drv.get_service(config.SERVICE_ACCOUNT_FILE)
            run_logger.upload_all(service, config.DRIVE_FOLDER_ID)
        except Exception as exc:
            log.warning(f"Falha ao enviar logs para Drive: {exc}")

    return {
        "run_id":          run_logger.run_id,
        "period":          f"{dates[0][:10]} → {dates[-1][:10]}",
        "weeks":           len(dates),
        "receptors":       len(receptors),
        "n_consents_db":   n_consents,
        "n_api_db":        n_api,
        "n_new_consents":  n_new_consents,
        "n_upd_consents":  n_upd_consents,
        "n_new_api":       n_new_api,
        "n_upd_api":       n_upd_api,
        "drive_folder_id": config.DRIVE_FOLDER_ID or "(não configurado)",
        "duration_s":      duration,
    }
