"""
test_api_status_weekly.py — Integration tests for api_status_weekly (feature 011).

Constitution II: real SQLite on disk (tmp_path), no mocking. Builds a small set of
api_requests with open_db()'s real DDL, runs the real refresh and asserts the rows.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

import compute_signals  # noqa: E402
import scrapers         # noqa: E402

FETCHED_AT = "2026-10-05T00:00:00+00:00"
W1, W2 = "2026-08-21", "2026-08-28"


@pytest.fixture
def con(tmp_path):
    c = scrapers.open_db(tmp_path / "status_test.db")
    yield c
    c.close()


def add_calls(con, week, receptor_uuid, receptor, transmitter_uuid, api, status, total, endpoint_id=1):
    con.execute(
        "INSERT OR REPLACE INTO api_requests "
        "(date, receptor, receptor_uuid, transmitter, transmitter_uuid, api, endpoint, "
        " endpoint_id, status, total, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (week, receptor, receptor_uuid, f"Transmissor {transmitter_uuid}", transmitter_uuid,
         api, "ep", endpoint_id, status, total, FETCHED_AT))
    con.commit()


def add_unique(con, week, receptor_uuid, receptor, total):
    con.execute(
        "INSERT OR REPLACE INTO unique_consents "
        "(date, receptor, receptor_uuid, cpf, cnpj, total, fetched_at) VALUES (?,?,?,?,?,?,?)",
        (week, receptor, receptor_uuid, total, 0, total, FETCHED_AT))
    con.commit()


def status_rows(con):
    return con.execute(
        "SELECT date, receptor_uuid, transmitter_uuid, status, total FROM api_status_weekly "
        "ORDER BY date, receptor_uuid, transmitter_uuid, status").fetchall()


def test_refresh_aggregates_by_week_receptor_transmitter_status(con):
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 200, 100)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "loans", 200, 50, endpoint_id=2)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 500, 7)
    add_calls(con, W2, "rec-a", "Alfa", "txm-2", "accounts", 200, 30)
    add_calls(con, W1, "rec-b", "Beta", "txm-1", "resources", 200, 9)

    scrapers.refresh_api_status_weekly(con)

    assert status_rows(con) == [
        (W1, "rec-b", "txm-1", 200, 9),
        (W2, "rec-a", "txm-1", 200, 150),
        (W2, "rec-a", "txm-1", 500, 7),
        (W2, "rec-a", "txm-2", 200, 30),
    ]


def test_refresh_excludes_consents_api(con):
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "consents", 200, 1_000)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 200, 10, endpoint_id=2)
    scrapers.refresh_api_status_weekly(con)
    assert status_rows(con) == [(W2, "rec-a", "txm-1", 200, 10)]


def test_refresh_is_idempotent_and_drops_stale_rows(con):
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 200, 10)
    scrapers.refresh_api_status_weekly(con)
    scrapers.refresh_api_status_weekly(con)
    assert status_rows(con) == [(W2, "rec-a", "txm-1", 200, 10)]

    con.execute("DELETE FROM api_requests")
    con.commit()
    scrapers.refresh_api_status_weekly(con)
    assert status_rows(con) == []


def test_success_total_matches_api_group_weekly(con):
    """Invariante (data-model.md): para receptor com consentimentos na semana e APIs
    mapeadas, a soma com status 200 é a mesma de api_group_weekly."""
    add_unique(con, W2, "rec-a", "Alfa", 50_000)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 200, 120)
    add_calls(con, W2, "rec-a", "Alfa", "txm-2", "loans", 200, 80, endpoint_id=2)
    add_calls(con, W2, "rec-a", "Alfa", "txm-2", "resources", 200, 15, endpoint_id=3)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 500, 40)

    scrapers.refresh_api_group_weekly(con)
    scrapers.refresh_api_status_weekly(con)

    agw = con.execute("SELECT SUM(req_week) FROM api_group_weekly WHERE date=? AND receptor_uuid=?",
                      (W2, "rec-a")).fetchone()[0]
    asw = con.execute("SELECT SUM(total) FROM api_status_weekly "
                      "WHERE date=? AND receptor_uuid=? AND status=200", (W2, "rec-a")).fetchone()[0]
    assert agw == asw == 215


def test_compute_signals_rebuilds_api_status_weekly(con):
    add_unique(con, W2, "rec-a", "Alfa", 50_000)
    add_calls(con, W2, "rec-a", "Alfa", "txm-1", "accounts", 500, 3)
    summary = compute_signals.compute(con)
    assert status_rows(con) == [(W2, "rec-a", "txm-1", 500, 3)]
    assert summary["api_status_secs"] >= 0
