"""
test_worker_persistence.py — o worker grava os dados antes de marcar 'ok'.

Regressão do bug de 2026-11-18: o worker marcava a tentativa como 'ok' em
fetch_attempts e mandava os registros pela queue para o processo principal
gravar. Com o principal morto (kill), os registros se perdiam, a tentativa
ficava 'ok' e o checkpoint (already_done) pulava o par na execução seguinte.

SQLite real em arquivo; só a fronteira de rede (Playwright/OpFSession e a
chamada ao portal) é substituída.
"""

import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

import scrapers  # noqa: E402
from scrapers import open_db  # noqa: E402
from telemetry import active_consents_target, already_done  # noqa: E402

DATES = ["2026-10-23", "2026-10-30"]
FETCHED_AT = "2026-11-19T10:00:00+00:00"
RUN_ID = "2026-11-19_10-00-00"
PAIR = {
    "receptor": {"label": "RECEPTOR A", "value": "rec-a"},
    "transmitter": {"label": "TRANSMISSOR B", "value": "txm-b"},
}
RAW = [
    {"value": 100, "date": "2026-10-23T00:00:00.000Z"},
    {"value": 120, "date": "2026-10-30T00:00:00.000Z"},
]


class _ListQueue:
    """Queue que ninguém consome — como quando o processo principal morreu."""

    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


@contextmanager
def _fake_playwright():
    yield object()


class _FakeSession:
    def __init__(self, _p):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "worker.db"
    open_db(path).close()
    return path


@pytest.fixture
def offline(monkeypatch):
    calls = []

    def _fetch(_session, receptor_uuid, transmitter_uuid, dates):
        calls.append((receptor_uuid, transmitter_uuid))
        return RAW

    monkeypatch.setattr(scrapers, "sync_playwright", _fake_playwright)
    monkeypatch.setattr(scrapers, "OpFSession", _FakeSession)
    monkeypatch.setattr(scrapers, "fetch_active_consents_for_org", _fetch)
    monkeypatch.setattr(scrapers.time, "sleep", lambda _s: None)
    return calls


def _run_worker(db_path):
    queue = _ListQueue()
    scrapers._worker_run_active_consents(
        1, [PAIR], DATES, FETCHED_AT, queue, 0, 0, str(db_path), RUN_ID,
    )
    return queue


def _attempt_status(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return [r[0] for r in con.execute(
            "SELECT status FROM fetch_attempts WHERE phase = 'active_consents'")]
    finally:
        con.close()


def test_worker_grava_dados_sem_o_processo_principal(db_path, offline):
    _run_worker(db_path)  # ninguém lê a queue

    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT date, total FROM active_consents "
        "WHERE receptor_uuid = 'rec-a' AND transmitter_uuid = 'txm-b' ORDER BY date"
    ).fetchall()
    con.close()

    assert rows == [("2026-10-23", 100), ("2026-10-30", 120)]
    assert _attempt_status(db_path) == ["ok"]


def test_falha_na_gravacao_nao_marca_ok(db_path, offline, monkeypatch):
    def _broken(_con, _records, _fetched_at):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(scrapers, "upsert_active_consents", _broken)
    _run_worker(db_path)

    target = active_consents_target("rec-a", DATES, "txm-b")
    assert _attempt_status(db_path) == ["failed"]
    assert not already_done(db_path, target)


def test_worker_orfao_para_sem_chamar_o_portal(db_path, offline, monkeypatch):
    monkeypatch.setattr(scrapers, "_parent_gone", lambda _pid: True)
    _run_worker(db_path)

    assert offline == []
    assert _attempt_status(db_path) == []
