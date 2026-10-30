"""
test_api_endpoint_weekly.py — Integration tests for api_endpoint_weekly (feature 012).

Constitution II: real SQLite on disk (tmp_path), no mocking. Builds api_requests rows with
open_db()'s real DDL, runs the real refresh and asserts the rows.

Convenção dos dados de teste: endpoint_id = 0 é a chamada "sem filtro de endpoint" (o
agregado da API); endpoint_id > 0 são os endpoints.
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

FETCHED_AT = "2026-10-29T00:00:00+00:00"
W1, W2 = "2026-08-21", "2026-08-28"
REC = ("rec-a", "Alfa")


@pytest.fixture
def con(tmp_path):
    c = scrapers.open_db(tmp_path / "endpoint_test.db")
    yield c
    c.close()


def add_calls(con, week, api, endpoint_id, total, *, status=200, transmitter="txm-1", receptor=REC):
    uuid, name = receptor
    con.execute(
        "INSERT OR REPLACE INTO api_requests "
        "(date, receptor, receptor_uuid, transmitter, transmitter_uuid, api, endpoint, "
        " endpoint_id, status, total, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (week, name, uuid, f"Transmissor {transmitter}", transmitter, api,
         f"Endpoint {endpoint_id}" if endpoint_id else "", endpoint_id, status, total, FETCHED_AT))
    con.commit()


def add_unique(con, week, total, receptor=REC):
    con.execute(
        "INSERT OR REPLACE INTO unique_consents "
        "(date, receptor, receptor_uuid, cpf, cnpj, total, fetched_at) VALUES (?,?,?,?,?,?,?)",
        (week, receptor[1], receptor[0], total, 0, total, FETCHED_AT))
    con.commit()


def rows(con):
    return con.execute(
        "SELECT date, receptor_uuid, api, endpoint_id, endpoint, total FROM api_endpoint_weekly "
        "ORDER BY date, receptor_uuid, api, endpoint_id").fetchall()


def test_refresh_sums_endpoints_across_transmitters_for_status_200_only(con):
    add_calls(con, W2, "accounts", 1, 100)
    add_calls(con, W2, "accounts", 1, 30, transmitter="txm-2")
    add_calls(con, W2, "accounts", 1, 9, status=500)
    add_calls(con, W2, "accounts", 2, 5)
    add_calls(con, W2, "accounts", 0, 135)                       # agregado fecha com 100 + 30 + 5

    scrapers.refresh_api_endpoint_weekly(con)

    assert rows(con) == [
        (W2, "rec-a", "accounts", 1, "Endpoint 1", 130),
        (W2, "rec-a", "accounts", 2, "Endpoint 2", 5),
    ]


def test_unattributed_calls_become_endpoint_zero_row(con):
    add_calls(con, W2, "accounts", 1, 100)
    add_calls(con, W2, "accounts", 0, 112)                       # 12 chamadas sem endpoint atribuído
    add_calls(con, W1, "loans", 3, 40)
    add_calls(con, W1, "loans", 0, 40)                           # fecha: nenhuma parcela
    add_calls(con, W1, "funds", 4, 7)                            # sem agregado: nenhuma parcela
    add_calls(con, W1, "exchanges", 5, 20)
    add_calls(con, W1, "exchanges", 0, 15)                       # agregado menor que a soma: nunca negativo

    scrapers.refresh_api_endpoint_weekly(con)

    by_key = {(r[0], r[2], r[3]): r[5] for r in rows(con)}
    assert by_key[(W2, "accounts", 0)] == 12
    assert (W2, "accounts", 1) in by_key and by_key[(W2, "accounts", 1)] == 100
    assert (W1, "loans", 0) not in by_key and (W1, "funds", 0) not in by_key
    assert (W1, "exchanges", 0) not in by_key and by_key[(W1, "exchanges", 5)] == 20
    zero = next(r for r in rows(con) if r[3] == 0)
    assert zero[4] == ""                                          # sem rótulo de endpoint


def test_unattributed_is_computed_after_summing_transmitters(con):
    add_calls(con, W2, "accounts", 1, 60, transmitter="txm-1")
    add_calls(con, W2, "accounts", 0, 70, transmitter="txm-1")   # +10 sem endpoint
    add_calls(con, W2, "accounts", 1, 40, transmitter="txm-2")
    add_calls(con, W2, "accounts", 0, 40, transmitter="txm-2")
    scrapers.refresh_api_endpoint_weekly(con)
    assert [(r[3], r[5]) for r in rows(con)] == [(0, 10), (1, 100)]


def test_refresh_excludes_consents_api(con):
    add_calls(con, W2, "consents", 21, 1_000)
    add_calls(con, W2, "consents", 0, 1_200)
    add_calls(con, W2, "accounts", 1, 10)
    scrapers.refresh_api_endpoint_weekly(con)
    assert [r[2] for r in rows(con)] == ["accounts"]


def test_refresh_is_idempotent_and_drops_stale_rows(con):
    add_calls(con, W2, "accounts", 1, 10)
    add_calls(con, W2, "accounts", 0, 12)
    scrapers.refresh_api_endpoint_weekly(con)
    first = rows(con)
    scrapers.refresh_api_endpoint_weekly(con)
    assert rows(con) == first and len(first) == 2

    con.execute("DELETE FROM api_requests")
    con.commit()
    scrapers.refresh_api_endpoint_weekly(con)
    assert rows(con) == []


def test_closes_with_the_api_aggregate(con):
    """I1 (data-model.md): por (data, receptor, API), a tabela soma o agregado da API."""
    add_calls(con, W2, "accounts", 1, 70)
    add_calls(con, W2, "accounts", 2, 20)
    add_calls(con, W2, "accounts", 0, 100)
    add_calls(con, W1, "customers", 6, 33)
    add_calls(con, W1, "customers", 0, 33)
    scrapers.refresh_api_endpoint_weekly(con)
    got = dict(((d, a), t) for d, a, t in con.execute(
        "SELECT date, api, SUM(total) FROM api_endpoint_weekly GROUP BY date, api").fetchall())
    assert got == {(W2, "accounts"): 100, (W1, "customers"): 33}


def test_group_totals_match_api_group_weekly(con):
    """I2: somando por grupo de API, o resultado é o de api_group_weekly (mesma base, status 200)."""
    add_unique(con, W2, 50_000)
    add_calls(con, W2, "accounts", 1, 100)
    add_calls(con, W2, "accounts", 0, 110)
    add_calls(con, W2, "loans", 2, 80, transmitter="txm-2")
    add_calls(con, W2, "loans", 0, 80, transmitter="txm-2")
    add_calls(con, W2, "accounts", 1, 40, status=500)
    add_calls(con, W2, "accounts", 0, 40, status=500)

    scrapers.refresh_api_group_weekly(con)
    scrapers.refresh_api_endpoint_weekly(con)

    agw = con.execute("SELECT SUM(req_week) FROM api_group_weekly WHERE date=? AND receptor_uuid=?",
                      (W2, "rec-a")).fetchone()[0]
    aew = con.execute("SELECT SUM(total) FROM api_endpoint_weekly WHERE date=? AND receptor_uuid=?",
                      (W2, "rec-a")).fetchone()[0]
    assert agw == aew == 190


def test_compute_signals_rebuilds_api_endpoint_weekly(con):
    add_unique(con, W2, 50_000)
    add_calls(con, W2, "accounts", 1, 5)
    summary = compute_signals.compute(con)
    assert rows(con) == [(W2, "rec-a", "accounts", 1, "Endpoint 1", 5)]
    assert summary["api_endpoint_secs"] >= 0
