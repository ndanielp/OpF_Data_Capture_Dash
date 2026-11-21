"""
test_payment_weekly.py — Integration tests for payment_weekly (feature 018).

Constitution II: real SQLite on disk (tmp_path), no mocking. Builds payment_api_requests rows
with open_db()'s real DDL, runs the real refresh and asserts the rows.
"""

import sys
from pathlib import Path

import pytest

_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

import compute_signals  # noqa: E402
import scrapers         # noqa: E402

FETCHED_AT = "2026-10-29T00:00:00+00:00"
W1, W2 = "2026-10-23", "2026-10-30"


@pytest.fixture
def con(tmp_path):
    c = scrapers.open_db(tmp_path / "payment_test.db")
    yield c
    c.close()


def add(con, week, api, endpoint_id, total, *, status=200, rec="ini-a", tx="det-1"):
    con.execute(
        "INSERT OR REPLACE INTO payment_api_requests "
        "(date, receptor, receptor_uuid, transmitter, transmitter_uuid, api, endpoint, "
        " endpoint_id, status, total, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (week, f"Iniciadora {rec}", rec, f"Detentora {tx}" if tx else "", tx, api,
         f"Endpoint {endpoint_id}" if endpoint_id else "", endpoint_id, status, total, FETCHED_AT))
    con.commit()


def rows(con):
    return con.execute(
        "SELECT date, receptor_uuid, transmitter_uuid, api, endpoint_id, status, total "
        "FROM payment_weekly ORDER BY date, receptor_uuid, transmitter_uuid, endpoint_id, status").fetchall()


def test_keeps_only_panel_endpoints_with_both_statuses(con):
    add(con, W1, "payments", 65, 100)
    add(con, W1, "payments", 65, 7, status=500)
    add(con, W1, "payments", 63, 900)               # Criar consentimento: fora do painel
    add(con, W1, "payments", 0, 1000)               # total da API: fora
    add(con, W1, "automatic-payments", 129, 50)
    add(con, W1, "enrollments", 133, 20)
    add(con, W1, "enrollments", 138, 40)            # autenticação FIDO2: fora
    scrapers.refresh_payment_weekly(con)
    assert rows(con) == [
        (W1, "ini-a", "det-1", "payments", 65, 200, 100),
        (W1, "ini-a", "det-1", "payments", 65, 500, 7),
        (W1, "ini-a", "det-1", "automatic-payments", 129, 200, 50),
        (W1, "ini-a", "det-1", "enrollments", 133, 200, 20),
    ]


def test_skips_rows_without_holder(con):
    add(con, W1, "payments", 65, 100, tx="")
    add(con, W1, "payments", 65, 30, tx="det-2")
    scrapers.refresh_payment_weekly(con)
    assert rows(con) == [(W1, "ini-a", "det-2", "payments", 65, 200, 30)]


def test_refresh_is_idempotent_and_follows_source(con):
    add(con, W1, "payments", 65, 100)
    add(con, W2, "payments", 65, 120)
    scrapers.refresh_payment_weekly(con)
    scrapers.refresh_payment_weekly(con)
    assert [r[-1] for r in rows(con)] == [100, 120]
    con.execute("DELETE FROM payment_api_requests WHERE date = ?", (W2,))
    con.commit()
    scrapers.refresh_payment_weekly(con)
    assert [r[0] for r in rows(con)] == [W1]


def test_compute_signals_refreshes_payment_weekly(con):
    add(con, W1, "automatic-payments", 129, 10)
    compute_signals.compute(con)
    assert rows(con) == [(W1, "ini-a", "det-1", "automatic-payments", 129, 200, 10)]
