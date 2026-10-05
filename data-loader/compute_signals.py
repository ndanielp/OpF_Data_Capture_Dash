"""
compute_signals.py — Calcula os alertas de mudança de comportamento (feature 010)
==================================================================================
Rode depois da coleta e antes do sync:

    python main.py run
    python compute_signals.py
    python sync_to_gcs.py        (ou .\\deploy.ps1 -SyncOnly no dashboard/)

Reconstrói behavior_signals inteira para todo o histórico, a partir do que existe
na base — não depende de a coleta ter terminado. Idempotente. Também reconstrói as
pré-agregações api_group_weekly e api_status_weekly (Dashboard 2.0).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import config    # noqa: E402
import scrapers  # noqa: E402
import signals   # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _detect_all(con: sqlite3.Connection) -> tuple[list[signals.Signal], dict]:
    """Carrega as séries e aplica todas as regras. Não escreve nada."""
    unique = signals.load_consent_series(con, "unique_consents")
    active = signals.load_consent_series(con, "active_consents")
    api_approved, api_skipped = signals.api_coverage(con)
    pivot, api_names = signals.load_api_pivot(con)
    debut_of = signals.first_seen(unique)
    volume_of = signals.volume_index(unique)

    found: list[signals.Signal] = []
    found += signals.detect_new_entrants(unique)
    found += signals.detect_consent_changes(unique, "unique_consents", debut_of, volume_of)
    found += signals.detect_consent_changes(active, "active_consents", debut_of, volume_of)
    found += signals.detect_api_changes(pivot, api_approved, api_names, volume_of)

    meta = {
        "consents_through": unique["date"].max() if not unique.empty else None,
        "api_through": pivot.index.max() if not pivot.empty else None,
        "api_skipped_weeks": api_skipped,
    }
    return found, meta


def _write(con: sqlite3.Connection, found: list[signals.Signal], meta: dict) -> None:
    """Substitui behavior_signals e behavior_signals_run numa única transação."""
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with con:  # commit no fim; rollback se qualquer passo falhar
        con.execute("DELETE FROM behavior_signals")
        con.executemany(
            """INSERT INTO behavior_signals
                   (week, signal_type, metric, api_group, receptor_uuid, receptor,
                    value_prev, value_curr, change_pct, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [tuple(s) for s in found],
        )
        con.execute(
            """INSERT OR REPLACE INTO behavior_signals_run
                   (id, computed_at, consents_through, api_through,
                    api_skipped_weeks, signals_total)
               VALUES (1, ?, ?, ?, ?, ?)""",
            (computed_at, meta["consents_through"], meta["api_through"],
             json.dumps(meta["api_skipped_weeks"]), len(found)),
        )


def compute(con: sqlite3.Connection) -> dict:
    """Pipeline completo sobre uma conexão aberta. Devolve um resumo para log/teste."""
    scrapers.refresh_api_group_weekly(con)
    t0 = time.perf_counter()
    scrapers.refresh_api_status_weekly(con)
    status_secs = time.perf_counter() - t0
    found, meta = _detect_all(con)
    _write(con, found, meta)
    by_type = Counter(s.signal_type for s in found)
    latest = meta["consents_through"]
    return {
        **meta,
        "total": len(found),
        "by_type": dict(by_type),
        "latest_week_count": sum(1 for s in found if s.week == latest),
        "api_status_secs": status_secs,
    }


def main() -> int:
    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        log.error("Banco não encontrado: %s", db_path)
        return 1
    con = scrapers.open_db(db_path)
    try:
        summary = compute(con)
    except sqlite3.Error as e:
        log.error("[ERRO] Falha ao calcular alertas (nada foi alterado): %s", e)
        return 1
    finally:
        con.close()

    log.info("api_group_weekly atualizado até %s", summary["api_through"])
    log.info("api_status_weekly reconstruída em %.1fs", summary["api_status_secs"])
    log.info("Trava de cobertura de API: %d semanas bloqueadas %s",
             len(summary["api_skipped_weeks"]), summary["api_skipped_weeks"] or "")
    t = summary["by_type"]
    log.info("Alertas calculados: %d (novos entrantes: %d | altas: %d | quedas: %d)",
             summary["total"], t.get("new_entrant", 0), t.get("increase", 0),
             t.get("decrease", 0))
    log.info("Semana mais recente (%s): %d alertas",
             summary["consents_through"], summary["latest_week_count"])
    log.info("[OK] behavior_signals reconstruída")
    return 0


if __name__ == "__main__":
    sys.exit(main())
