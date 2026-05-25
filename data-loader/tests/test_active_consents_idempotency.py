"""
test_active_consents_idempotency.py — Integration tests for already_done() checkpoint.

Constitution II: uses real in-memory SQLite, no mocking.
Tests:
  1. already_done() returns False before any collection attempt.
  2. After log_attempt with status='ok', already_done() returns True for same target.
  3. After log_attempt with status='empty', already_done() returns True (empty = done).
  4. After log_attempt with status='failed', already_done() returns False (not done).
  5. active_consents_target() produces canonical target string.
  6. No duplicate fetch_attempts rows for same target on re-collection.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

from scrapers import open_db  # noqa: E402
from telemetry import (  # noqa: E402
    active_consents_target,
    already_done,
    log_attempt,
)

RECEPTOR_UUID = "rec-uuid-checkpoint-001"
DATES = ["2026-05-12", "2026-05-19"]
RUN_ID = "2026-05-25_12-00-00"
STARTED_AT = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_checkpoint.db"
    con = open_db(path)
    con.close()
    return path


def test_active_consents_target_format():
    target = active_consents_target(RECEPTOR_UUID, DATES)
    assert target == f"active_consents|||{RECEPTOR_UUID}|{DATES[0]}_{DATES[-1]}"


def test_not_done_before_any_attempt(db_path):
    target = active_consents_target(RECEPTOR_UUID, DATES)
    assert already_done(db_path, target) is False


def test_done_after_ok_status(db_path):
    target = active_consents_target(RECEPTOR_UUID, DATES)
    log_attempt(db_path, RUN_ID, "active_consents", target, STARTED_AT, 250, "ok",
                records_count=3)
    assert already_done(db_path, target) is True


def test_done_after_empty_status(db_path):
    target = active_consents_target(RECEPTOR_UUID, ["2026-04-28", "2026-05-05"])
    log_attempt(db_path, RUN_ID, "active_consents", target, STARTED_AT, 180, "empty",
                records_count=0)
    assert already_done(db_path, target) is True


def test_not_done_after_failed_status(db_path):
    """A failed attempt does NOT count as done — must retry."""
    target = active_consents_target(RECEPTOR_UUID, ["2026-05-05", "2026-05-12"])
    log_attempt(db_path, RUN_ID, "active_consents", target, STARTED_AT, 500, "failed",
                error_class="OpFTransientError", error_msg="timeout")
    assert already_done(db_path, target) is False


def test_no_duplicate_active_consents_rows_on_two_runs(db_path, tmp_path):
    """Simulates two collection runs for same receptor+date: active_consents has no dups."""
    from scrapers import upsert_active_consents

    records = [
        {
            "receptor_uuid":    RECEPTOR_UUID,
            "transmitter_uuid": "tra-uuid-X",
            "date":             "2026-05-19",
            "total":            42,
            "cpf":              None,
            "cnpj":             None,
            "fetched_at":       STARTED_AT,
        }
    ]
    con = sqlite3.connect(str(db_path))

    # First run.
    upsert_active_consents(con, records, STARTED_AT)
    con.commit()

    # Second run with updated total.
    records_updated = [{**records[0], "total": 99}]
    upsert_active_consents(con, records_updated, STARTED_AT)
    con.commit()

    count = con.execute("SELECT COUNT(*) FROM active_consents").fetchone()[0]
    assert count == 1, "Only one row — upsert must not duplicate"

    total = con.execute(
        "SELECT total FROM active_consents WHERE receptor_uuid=? AND transmitter_uuid=?",
        (RECEPTOR_UUID, "tra-uuid-X"),
    ).fetchone()[0]
    assert total == 99, "Updated total after second run"
    con.close()


def test_already_done_uses_today_boundary(db_path):
    """already_done() with run_id=None checks same calendar day (cross-run resumability)."""
    target = active_consents_target("rec-uuid-crossrun", DATES)
    # Log with a different run_id than any we'd pass.
    log_attempt(db_path, "2026-05-25_08-00-00", "active_consents", target,
                STARTED_AT, 200, "ok", records_count=5)
    # Should still be found when called without run_id (today check).
    assert already_done(db_path, target, run_id=None) is True
