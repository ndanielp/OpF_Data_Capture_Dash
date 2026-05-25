"""
test_active_consents_upsert.py — Integration tests for active_consents DB layer.

Constitution II: uses real in-memory SQLite, no mocking.
Tests:
  1. open_db() creates the active_consents table with correct schema.
  2. upsert_active_consents() inserts rows and returns correct count.
  3. Row values are stored and readable with correct types.
  4. Re-upserting with same PK (receptor×transmitter×date) updates — no duplicate rows.
  5. cpf/cnpj are nullable — absent in source maps to NULL in DB.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add data-loader root to sys.path so imports resolve without installation.
_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

from scrapers import open_db, upsert_active_consents  # noqa: E402


FETCHED_AT = "2026-05-25T12:00:00+00:00"

SAMPLE_RECORDS = [
    {
        "receptor_uuid":    "rec-uuid-001",
        "transmitter_uuid": "tra-uuid-AAA",
        "date":             "2026-05-19",
        "total":            150,
        "cpf":              100,
        "cnpj":             50,
        "fetched_at":       FETCHED_AT,
    },
    {
        "receptor_uuid":    "rec-uuid-001",
        "transmitter_uuid": "tra-uuid-BBB",
        "date":             "2026-05-19",
        "total":            75,
        "cpf":              None,
        "cnpj":             None,
        "fetched_at":       FETCHED_AT,
    },
    {
        "receptor_uuid":    "rec-uuid-002",
        "transmitter_uuid": "tra-uuid-AAA",
        "date":             "2026-05-19",
        "total":            30,
        "cpf":              20,
        "cnpj":             10,
        "fetched_at":       FETCHED_AT,
    },
]


@pytest.fixture
def in_memory_db(tmp_path):
    """Opens a real SQLite DB in tmp_path (not :memory:) so open_db can create files."""
    db_path = tmp_path / "test_consents.db"
    con = open_db(db_path)
    yield con, db_path
    con.close()


def test_open_db_creates_active_consents_table(in_memory_db):
    con, _ = in_memory_db
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "active_consents" in tables


def test_open_db_active_consents_columns(in_memory_db):
    con, _ = in_memory_db
    cols = {r[1] for r in con.execute("PRAGMA table_info(active_consents)").fetchall()}
    assert {"receptor_uuid", "transmitter_uuid", "date", "total",
            "cpf", "cnpj", "fetched_at"}.issubset(cols)


def test_open_db_active_consents_primary_key(in_memory_db):
    con, _ = in_memory_db
    pk_cols = {
        r[1] for r in con.execute("PRAGMA table_info(active_consents)").fetchall()
        if r[5] > 0
    }
    assert pk_cols == {"receptor_uuid", "transmitter_uuid", "date"}


def test_upsert_returns_correct_count(in_memory_db):
    con, _ = in_memory_db
    n = upsert_active_consents(con, SAMPLE_RECORDS, FETCHED_AT)
    con.commit()
    assert n == len(SAMPLE_RECORDS)


def test_upsert_rows_readable(in_memory_db):
    con, _ = in_memory_db
    upsert_active_consents(con, SAMPLE_RECORDS, FETCHED_AT)
    con.commit()

    rows = con.execute(
        "SELECT receptor_uuid, transmitter_uuid, date, total, cpf, cnpj "
        "FROM active_consents ORDER BY receptor_uuid, transmitter_uuid"
    ).fetchall()

    assert len(rows) == 3
    # First row: rec-001 × tra-AAA
    r0 = rows[0]
    assert r0[0] == "rec-uuid-001"
    assert r0[1] == "tra-uuid-AAA"
    assert r0[2] == "2026-05-19"
    assert r0[3] == 150
    assert r0[4] == 100   # cpf
    assert r0[5] == 50    # cnpj


def test_upsert_nullable_cpf_cnpj(in_memory_db):
    con, _ = in_memory_db
    upsert_active_consents(con, SAMPLE_RECORDS, FETCHED_AT)
    con.commit()

    row = con.execute(
        "SELECT cpf, cnpj FROM active_consents "
        "WHERE receptor_uuid='rec-uuid-001' AND transmitter_uuid='tra-uuid-BBB'"
    ).fetchone()
    assert row is not None
    assert row[0] is None   # cpf absent → NULL
    assert row[1] is None   # cnpj absent → NULL


def test_upsert_no_duplicates_on_rerun(in_memory_db):
    """Re-upserting same PK updates values, not duplicate rows (FR-005)."""
    con, _ = in_memory_db
    upsert_active_consents(con, SAMPLE_RECORDS, FETCHED_AT)
    con.commit()

    # Re-upsert with updated totals.
    updated = [{**r, "total": r["total"] + 999} for r in SAMPLE_RECORDS]
    upsert_active_consents(con, updated, FETCHED_AT)
    con.commit()

    count = con.execute("SELECT COUNT(*) FROM active_consents").fetchone()[0]
    assert count == len(SAMPLE_RECORDS), "No duplicate rows after re-upsert"

    # Verify values were updated, not appended.
    row = con.execute(
        "SELECT total FROM active_consents "
        "WHERE receptor_uuid='rec-uuid-001' AND transmitter_uuid='tra-uuid-AAA'"
    ).fetchone()
    assert row[0] == 150 + 999


def test_upsert_does_not_commit_automatically(in_memory_db):
    """upsert_active_consents() must NOT auto-commit (caller controls transaction)."""
    con, db_path = in_memory_db
    upsert_active_consents(con, SAMPLE_RECORDS, FETCHED_AT)
    # Do NOT call con.commit()

    # Open a second connection; rows should not be visible yet.
    con2 = sqlite3.connect(str(db_path))
    count = con2.execute("SELECT COUNT(*) FROM active_consents").fetchone()[0]
    con2.close()
    assert count == 0, "Rows must not be visible before commit"
