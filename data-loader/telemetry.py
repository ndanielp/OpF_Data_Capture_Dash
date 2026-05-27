"""
telemetry.py — Writer de eventos de coleta e checkpoint resumable
==================================================================
Duas tabelas persistentes em consents.db:

- `fetch_attempts`: 1 linha por tentativa de chamada HTTP à API OpF
  (inclui sucesso, vazio, falha). Alimenta checkpoint resumable e
  validação de taxa de sucesso.

- `run_summary`:    1 linha por execução (`run_id`) com contadores
  agregados. Alimenta a "Saúde da Coleta".

O writer é stateless em relação ao processo que chama — os workers
multiprocess abrem suas próprias conexões SQLite e escrevem diretamente.
O banco roda em WAL mode (configurado em scrapers.open_db) para suportar
escritas concorrentes.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


# ── Schema (chamado por scrapers.open_db) ─────────────────────────────────────

TELEMETRY_DDL = """
CREATE TABLE IF NOT EXISTS fetch_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    phase         TEXT NOT NULL,
    target        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    duration_ms   INTEGER,
    status        TEXT NOT NULL,
    http_status   INTEGER,
    error_class   TEXT,
    error_msg     TEXT,
    records_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_fetch_attempts_run
    ON fetch_attempts(run_id);
CREATE INDEX IF NOT EXISTS idx_fetch_attempts_target
    ON fetch_attempts(target, status);

CREATE TABLE IF NOT EXISTS run_summary (
    run_id                TEXT PRIMARY KEY,
    started_at            TEXT NOT NULL,
    ended_at              TEXT,
    phase_consents_ok     INTEGER NOT NULL DEFAULT 0,
    phase_consents_failed INTEGER NOT NULL DEFAULT 0,
    phase_api_ok          INTEGER NOT NULL DEFAULT 0,
    phase_api_failed      INTEGER NOT NULL DEFAULT 0,
    phase_api_skipped     INTEGER NOT NULL DEFAULT 0,
    total_upserted        INTEGER NOT NULL DEFAULT 0
);
"""


def ensure_tables(con: sqlite3.Connection) -> None:
    """Cria tabelas de telemetria se não existirem. Idempotente."""
    con.executescript(TELEMETRY_DDL)
    con.commit()
    # Migração: adiciona colunas novas em DBs existentes.
    for _col_ddl in [
        "ALTER TABLE run_summary ADD COLUMN phase_api_skipped INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE run_summary ADD COLUMN phase_active_consents_ok INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE run_summary ADD COLUMN phase_active_consents_failed INTEGER NOT NULL DEFAULT 0",
    ]:
        try:
            con.execute(_col_ddl)
            con.commit()
        except sqlite3.OperationalError:
            pass  # coluna já existe


# ── Target canônico ───────────────────────────────────────────────────────────

def consents_target(receptor_uuid: str, date_first: str, date_last: str) -> str:
    return f"consents|||{receptor_uuid}|{date_first}_{date_last}"


def active_consents_target(
    receptor_uuid: str, dates: list[str], transmitter_uuid: str = "",
) -> str:
    """Target canônico para uma tentativa de coleta de consentimentos ativos.

    Inclui transmitter_uuid para checkpoint granular por par receptor×transmissor
    — a API /api/consents retorna um agregado por chamada, então iteramos um par
    por request. transmitter_uuid omitido (padrão "") preserva compatibilidade
    com chamadas sem filtro de transmissor (coleta agregada).
    """
    txm = transmitter_uuid or ""
    return f"active_consents|||{receptor_uuid}|||{txm}|{dates[0][:10]}_{dates[-1][:10]}"


def api_target(
    api: str,
    endpoint_id: int,
    status: int,
    receptor_uuid: str,
    transmitter_uuid: str,
    date_first: str,
    date_last: str,
) -> str:
    return (
        f"api_requests|{api}|{endpoint_id}|{status}|"
        f"{receptor_uuid}|{transmitter_uuid}|{date_first}_{date_last}"
    )


def probe_transmitter_target(
    receptor_uuid: str, transmitter_uuid: str, date_first: str, date_last: str
) -> str:
    return f"probe_transmitter|{receptor_uuid}|{transmitter_uuid}|{date_first}_{date_last}"


def probe_api_target(
    api: str, receptor_uuid: str, transmitter_uuid: str, date_first: str, date_last: str
) -> str:
    return f"probe_api|{api}|{receptor_uuid}|{transmitter_uuid}|{date_first}_{date_last}"


# ── Writers ───────────────────────────────────────────────────────────────────

def log_attempt(
    db_path: Path | str,
    run_id: str,
    phase: str,
    target: str,
    started_at: str,
    duration_ms: int,
    status: str,
    http_status: int | None = None,
    error_class: str | None = None,
    error_msg: str | None = None,
    records_count: int = 0,
) -> None:
    """Insere uma tentativa em `fetch_attempts`.

    status ∈ {'ok', 'empty', 'failed', 'skipped'}.
    """
    try:
        con = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            con.execute(
                """
                INSERT INTO fetch_attempts
                    (run_id, phase, target, started_at, duration_ms,
                     status, http_status, error_class, error_msg, records_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, phase, target, started_at, duration_ms,
                 status, http_status, error_class, error_msg, records_count),
            )
            con.commit()
        finally:
            con.close()
    except Exception as exc:
        # Telemetria nunca pode quebrar a coleta.
        log.warning("telemetry.log_attempt falhou: %s", exc)


def already_done(
    db_path: Path | str,
    target: str,
    run_id: str | None = None,
) -> bool:
    """Retorna True se esse `target` já foi coletado com sucesso
    (`status='ok'` ou `status='empty'`) no run_id atual ou no dia atual.

    Se run_id for None, considera o dia atual — isso dá resumability
    cross-run dentro do mesmo dia.
    """
    try:
        con = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            if run_id is not None:
                row = con.execute(
                    """
                    SELECT 1 FROM fetch_attempts
                    WHERE target = ? AND run_id = ? AND status IN ('ok', 'empty')
                    LIMIT 1
                    """,
                    (target, run_id),
                ).fetchone()
            else:
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                row = con.execute(
                    """
                    SELECT 1 FROM fetch_attempts
                    WHERE target = ?
                      AND status IN ('ok', 'empty')
                      AND started_at LIKE ?
                    LIMIT 1
                    """,
                    (target, f"{today}%"),
                ).fetchone()
            return row is not None
        finally:
            con.close()
    except Exception as exc:
        log.warning("telemetry.already_done falhou: %s", exc)
        return False  # Em caso de dúvida, prefere coletar novamente.


def start_run(db_path: Path | str, run_id: str) -> None:
    started = datetime.now(timezone.utc).isoformat()
    try:
        con = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO run_summary (run_id, started_at)
                VALUES (?, ?)
                """,
                (run_id, started),
            )
            con.commit()
        finally:
            con.close()
    except Exception as exc:
        log.warning("telemetry.start_run falhou: %s", exc)


def finalize_run(
    db_path: Path | str,
    run_id: str,
    total_upserted: int = 0,
) -> dict:
    """Atualiza `run_summary` agregando contagens de `fetch_attempts`.

    Retorna um dict com o resumo (útil para logging)."""
    ended = datetime.now(timezone.utc).isoformat()
    try:
        con = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            stats = con.execute(
                """
                SELECT
                    SUM(CASE WHEN phase='consents' AND status IN ('ok','empty') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='consents' AND status='failed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='active_consents' AND status IN ('ok','empty') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='active_consents' AND status='failed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='api_requests' AND status IN ('ok','empty') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='api_requests' AND status='failed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN phase='api_requests' AND status='skipped' THEN 1 ELSE 0 END)
                FROM fetch_attempts
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            (cons_ok, cons_fail,
             ac_ok, ac_fail,
             api_ok, api_fail, api_skipped) = [x or 0 for x in stats]

            con.execute(
                """
                UPDATE run_summary
                SET ended_at = ?,
                    phase_consents_ok = ?,
                    phase_consents_failed = ?,
                    phase_active_consents_ok = ?,
                    phase_active_consents_failed = ?,
                    phase_api_ok = ?,
                    phase_api_failed = ?,
                    phase_api_skipped = ?,
                    total_upserted = ?
                WHERE run_id = ?
                """,
                (ended, cons_ok, cons_fail, ac_ok, ac_fail,
                 api_ok, api_fail, api_skipped, total_upserted, run_id),
            )
            con.commit()

            return {
                "run_id": run_id,
                "ended_at": ended,
                "phase_consents_ok": cons_ok,
                "phase_consents_failed": cons_fail,
                "phase_active_consents_ok": ac_ok,
                "phase_active_consents_failed": ac_fail,
                "phase_api_ok": api_ok,
                "phase_api_failed": api_fail,
                "phase_api_skipped": api_skipped,
                "total_upserted": total_upserted,
            }
        finally:
            con.close()
    except Exception as exc:
        log.warning("telemetry.finalize_run falhou: %s", exc)
        return {"run_id": run_id, "error": str(exc)}
