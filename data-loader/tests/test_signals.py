"""
test_signals.py — Integration tests for behavior_signals (feature 010).

Constitution II: real SQLite on disk (tmp_path), no mocking. Every test builds a
small synthetic history with open_db()'s real DDL, runs the real pipeline
(compute_signals.compute) and asserts the rows written to behavior_signals.
Thresholds come from signals.py constants — tests never restate the numbers.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

_LOADER_ROOT = Path(__file__).parent.parent
if str(_LOADER_ROOT) not in sys.path:
    sys.path.insert(0, str(_LOADER_ROOT))

import compute_signals  # noqa: E402
import signals as S     # noqa: E402
from scrapers import open_db  # noqa: E402

FETCHED_AT = "2026-09-23T00:00:00+00:00"
N_WEEKS = 60
WEEKS = [d.strftime("%Y-%m-%d") for d in pd.date_range("2024-01-05", periods=N_WEEKS, freq="7D")]


# ── Fixtures / helpers ────────────────────────────────────────────────────────

@pytest.fixture
def con(tmp_path):
    c = open_db(tmp_path / "signals_test.db")
    yield c
    c.close()


def add_unique(con, uuid, name, values, start=0):
    """values[i] vai para WEEKS[start + i]; None pula a semana."""
    rows = [(WEEKS[start + i], name, uuid, 0, 0, int(v), FETCHED_AT)
            for i, v in enumerate(values) if v is not None]
    con.executemany(
        "INSERT OR REPLACE INTO unique_consents "
        "(date, receptor, receptor_uuid, cpf, cnpj, total, fetched_at) VALUES (?,?,?,?,?,?,?)",
        rows)
    con.commit()


def add_active(con, uuid, name, values, start=0):
    rows = [(uuid, "txm-1", name, "Transmissor", WEEKS[start + i], int(v), FETCHED_AT)
            for i, v in enumerate(values) if v is not None]
    con.executemany(
        "INSERT OR REPLACE INTO active_consents "
        "(receptor_uuid, transmitter_uuid, receptor, transmitter, date, total, fetched_at) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()


def add_api(con, uuid, name, api, values, start=0):
    """Chamadas status 200. api_group_weekly faz JOIN com unique_consents na mesma
    semana, então o receptor precisa ter consentimentos nessas semanas."""
    rows = [(WEEKS[start + i], name, uuid, "Transmissor", "txm-1", api, "ep", 1, 200, int(v), FETCHED_AT)
            for i, v in enumerate(values) if v is not None]
    con.executemany(
        "INSERT OR REPLACE INTO api_requests "
        "(date, receptor, receptor_uuid, transmitter, transmitter_uuid, api, endpoint, "
        " endpoint_id, status, total, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()


def signals_rows(con, **where):
    sql = "SELECT * FROM behavior_signals"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql + " ORDER BY week, receptor_uuid", tuple(where.values()))]
    con.row_factory = None
    return rows


def established(con, uuid="rec-est", name="Estabelecido", level=100_000):
    """Receptor presente desde a primeira semana, estável — fixa o início da série."""
    add_unique(con, uuid, name, [level] * N_WEEKS)


# ── Foundational: pipeline, idempotência, refresh (T008) ──────────────────────

def test_empty_database_runs_and_records_run(con):
    summary = compute_signals.compute(con)
    assert summary["total"] == 0
    run = con.execute("SELECT id, signals_total, api_skipped_weeks FROM behavior_signals_run").fetchall()
    assert run == [(1, 0, "[]")]


def test_compute_is_idempotent(con):
    established(con)
    add_unique(con, "rec-new", "Novo Banco", [40_000] * 10, start=30)
    add_api(con, "rec-est", "Estabelecido", "accounts", [2_000_000] * N_WEEKS)

    compute_signals.compute(con)
    first = signals_rows(con)
    compute_signals.compute(con)
    second = signals_rows(con)

    assert first == second
    assert con.execute("SELECT COUNT(*) FROM behavior_signals_run").fetchone()[0] == 1


def test_refreshes_stale_api_group_weekly(con):
    """Reproduz o caso real de 2026-09-23: api_group_weekly parada semanas atrás."""
    established(con)
    add_api(con, "rec-est", "Estabelecido", "accounts", [2_000_000] * N_WEEKS)
    con.execute("DELETE FROM api_group_weekly")
    con.commit()

    summary = compute_signals.compute(con)

    last_agw = con.execute("SELECT MAX(date) FROM api_group_weekly").fetchone()[0]
    assert last_agw == WEEKS[-1]
    assert summary["api_through"] == WEEKS[-1]


def test_write_is_atomic_on_failure(con, monkeypatch):
    """Erro no meio da escrita não deixa a tabela pela metade nem apaga a anterior."""
    established(con)
    con.execute("INSERT INTO behavior_signals (week, signal_type, metric, receptor_uuid, value_curr) "
                "VALUES ('2024-01-05', 'increase', 'unique_consents', 'old', 1)")
    con.commit()

    good = S.Signal("2024-01-05", "decrease", "unique_consents", "", "new", "new", None, 1.0, None, 0)
    bad = S.Signal("2024-01-05", "increase", "unique_consents", "", "x", "x", None, 1.0, None, 0)
    monkeypatch.setattr(compute_signals, "_detect_all",
                        lambda c: ([good, bad, bad], [], {"consents_through": None, "api_through": None,
                                                          "api_skipped_weeks": []}))
    with pytest.raises(sqlite3.IntegrityError):
        compute_signals.compute(con)

    # O DELETE e a linha válida inserida antes do erro foram desfeitos juntos.
    assert [r["receptor_uuid"] for r in signals_rows(con)] == ["old"]


# ── US1: novos entrantes (T014) ───────────────────────────────────────────────

def _new_entrants(con):
    return {r["receptor_uuid"]: r for r in signals_rows(con, signal_type="new_entrant")}


def test_new_entrant_slow_debut_then_fast_growth(con):
    """Caso Banco Inter: estreia minúscula e cruza o piso crescendo rápido."""
    established(con)
    add_unique(con, "rec-inter", "Banco Inter", [271, 1_000, 5_000, 20_000, 40_000, 60_000, 90_000], start=10)
    compute_signals.compute(con)
    ne = _new_entrants(con)
    assert ne["rec-inter"]["week"] == WEEKS[14]
    assert ne["rec-inter"]["value_prev"] == 271
    assert ne["rec-inter"]["value_curr"] == 40_000
    assert ne["rec-inter"]["volume"] == 40_000


def test_new_entrant_big_debut(con):
    """Caso Shopee: já estreia acima do piso."""
    established(con)
    add_unique(con, "rec-shopee", "Shopee", [3_245_941, 3_400_000, 3_500_000], start=20)
    compute_signals.compute(con)
    ne = _new_entrants(con)["rec-shopee"]
    assert ne["week"] == WEEKS[20]
    assert ne["value_prev"] is None and ne["change_pct"] is None


def test_no_new_entrant_below_floor(con):
    """Cresce rápido mas nunca chega ao piso (Cumbuca nas primeiras semanas, Google Pay)."""
    established(con)
    add_unique(con, "rec-small", "Pequena IP", [4, 100, 1_000, 10_000, 25_000, S.NEW_ENTRANT_FLOOR - 1], start=10)
    compute_signals.compute(con)
    assert "rec-small" not in _new_entrants(con)


def test_no_new_entrant_slow_growth_across_floor(con):
    """Caso Geru: passa do piso, mas devagar — não é crescimento acelerado."""
    established(con)
    add_unique(con, "rec-slow", "Crescimento Lento", [26_000, 27_000, 28_000, 29_000, 31_000, 32_000], start=10)
    compute_signals.compute(con)
    assert "rec-slow" not in _new_entrants(con)


def test_receptor_present_at_series_start_is_never_new(con):
    add_unique(con, "rec-old", "Antigo", [100, 1_000, 50_000, 90_000] + [90_000] * (N_WEEKS - 4))
    compute_signals.compute(con)
    assert "rec-old" not in _new_entrants(con)


def test_new_entrant_fires_only_once(con):
    established(con)
    add_unique(con, "rec-twice", "Duas Vezes", [100, 50_000, 10_000, 10_000, 10_000, 10_000, 60_000], start=10)
    compute_signals.compute(con)
    assert len([r for r in signals_rows(con, signal_type="new_entrant") if r["receptor_uuid"] == "rec-twice"]) == 1


def test_no_new_entrant_after_window(con):
    """Cruzar o piso depois de 26 semanas não é mais 'novo'."""
    established(con)
    late = [1_000] * (S.NEW_WINDOW_WEEKS + 2) + [40_000, 60_000]
    add_unique(con, "rec-late", "Tardio", late, start=5)
    compute_signals.compute(con)
    assert "rec-late" not in _new_entrants(con)


# ── US2: altas (T019, T020) ───────────────────────────────────────────────────

def test_consent_increase_immediate(con):
    level = 100_000
    add_unique(con, "rec-up", "Sobe", [level] * 40 + [int(level * 1.3)] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, signal_type="increase", metric="unique_consents")
    assert [(r["receptor_uuid"], r["week"]) for r in rows] == [("rec-up", WEEKS[40])]
    assert rows[0]["value_prev"] == level
    assert rows[0]["change_pct"] == pytest.approx(0.3)


def test_active_consents_increase(con):
    established(con, "rec-act", "Ativos Sobe")
    add_active(con, "rec-act", "Ativos Sobe", [200_000] * 40 + [260_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, signal_type="increase", metric="active_consents")
    assert [(r["receptor_uuid"], r["week"]) for r in rows] == [("rec-act", WEEKS[40])]


def test_no_consent_increase_for_young_receptor(con):
    """Nas primeiras 26 semanas o receptor só pode gerar alerta de novo entrante."""
    established(con)
    add_unique(con, "rec-young", "Jovem", [100_000] * 10 + [150_000] * 5, start=20)
    compute_signals.compute(con)
    assert signals_rows(con, signal_type="increase", receptor_uuid="rec-young") == []


def test_no_consent_increase_below_floor_or_small_change(con):
    add_unique(con, "rec-tiny", "Pequeno", [20_000] * 40 + [30_000] * (N_WEEKS - 40))   # +50%, base < piso
    add_unique(con, "rec-mild", "Moderado", [100_000] * 40 + [115_000] * (N_WEEKS - 40))  # +15%
    compute_signals.compute(con)
    assert signals_rows(con, signal_type="increase") == []


def _api_scenario(con, target_values, control=50_000_000, grp_api="accounts"):
    """Receptor-alvo e um controle grande no mesmo grupo de API, ambos estabelecidos.
    O controle grande mantém o movimento do ecossistema quase parado."""
    established(con, "rec-a", "Alvo")
    established(con, "rec-b", "Controle")
    add_api(con, "rec-a", "Alvo", grp_api, target_values)
    add_api(con, "rec-b", "Controle", grp_api, [control] * N_WEEKS)


def test_api_increase_confirmed_on_second_week(con):
    # Degrau 2M → 6M na semana 40: a razão relativa passa de API_UP em 42 e 43,
    # então o alerta sai em 43 (confirmado), e só uma vez.
    _api_scenario(con, [2_000_000] * 40 + [6_000_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, signal_type="increase", metric="api_group")
    assert [(r["receptor_uuid"], r["api_group"], r["week"]) for r in rows] == [("rec-a", "Conta", WEEKS[43])]
    assert rows[0]["value_prev"] == pytest.approx(2_000_000)


def test_api_increase_not_confirmed_yet(con):
    """Condição verdadeira só na última semana da base → ainda sem alerta."""
    _api_scenario(con, [2_000_000] * 57 + [6_000_000] * 3)
    compute_signals.compute(con)
    assert signals_rows(con, metric="api_group") == []


def watch_rows(con):
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM behavior_watch ORDER BY receptor_uuid, api_group")]
    con.row_factory = None
    return rows


def test_api_condition_on_last_week_goes_to_watch(con):
    """Feature 011 (FR-030): condição vista só na última semana fica 'em observação',
    com a semana que vai confirmar ou descartar."""
    _api_scenario(con, [2_000_000] * 57 + [6_000_000] * 3)
    compute_signals.compute(con)
    rows = watch_rows(con)
    assert [(r["receptor_uuid"], r["api_group"], r["direction"], r["week"]) for r in rows] == [
        ("rec-a", "Conta", "increase", WEEKS[-1])]
    assert rows[0]["confirm_week"] == (pd.Timestamp(WEEKS[-1]) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    assert rows[0]["value_prev"] == pytest.approx(2_000_000)
    assert signals_rows(con, metric="api_group") == []


def test_confirmed_api_alert_is_not_in_watch_and_rebuild_is_idempotent(con):
    _api_scenario(con, [2_000_000] * 40 + [6_000_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    compute_signals.compute(con)
    assert watch_rows(con) == []
    assert len(signals_rows(con, metric="api_group")) == 1


def test_active_consents_floor_is_measured_in_unique(con):
    """Feature 011 (FR-032): ativos acima de 30 mil não bastam — o piso vale para
    os únicos da semana-base."""
    established(con, "rec-small", "Pequena", level=20_000)
    add_active(con, "rec-small", "Pequena", [40_000] * 40 + [60_000] * (N_WEEKS - 40))
    established(con, "rec-big", "Grande", level=100_000)
    add_active(con, "rec-big", "Grande", [200_000] * 40 + [260_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, metric="active_consents")
    assert [(r["receptor_uuid"], r["signal_type"]) for r in rows] == [("rec-big", "increase")]


def test_api_ecosystem_wide_rise_is_not_a_signal(con):
    established(con, "rec-a", "Alvo")
    established(con, "rec-b", "Controle")
    add_api(con, "rec-a", "Alvo", "accounts", [2_000_000] * 40 + [6_000_000] * (N_WEEKS - 40))
    add_api(con, "rec-b", "Controle", "accounts", [2_000_000] * 40 + [6_000_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    assert signals_rows(con, metric="api_group") == []


def test_api_below_floor_is_not_a_signal(con):
    _api_scenario(con, [S.API_FLOOR // 2] * 40 + [S.API_FLOOR * 2] * (N_WEEKS - 40))
    compute_signals.compute(con)
    assert signals_rows(con, metric="api_group") == []


def test_api_blocked_weeks_never_signal(con):
    """detect_api_changes só emite em semanas aprovadas pela trava de cobertura."""
    _api_scenario(con, [2_000_000] * 40 + [6_000_000] * (N_WEEKS - 40))
    compute_signals.compute(con)   # garante api_group_weekly
    pivot, names = S.load_api_pivot(con)
    approved = set(WEEKS) - {WEEKS[42], WEEKS[43]}
    found = S.detect_api_changes(pivot, approved, names, {})
    assert [s for s in found if s.receptor_uuid == "rec-a"] == []


# ── US3: quedas (T026, T027) ──────────────────────────────────────────────────

def test_consent_decrease_immediate(con):
    add_unique(con, "rec-down", "Cai", [100_000] * 40 + [60_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, signal_type="decrease", metric="unique_consents")
    assert [(r["receptor_uuid"], r["week"]) for r in rows] == [("rec-down", WEEKS[40])]
    assert rows[0]["change_pct"] == pytest.approx(-0.4)


def test_missing_week_is_not_a_drop(con):
    """Semana sem coleta não é zero: compara-se com a última observação."""
    add_unique(con, "rec-gap", "Com Buraco", [100_000] * 40 + [None] + [100_000] * (N_WEEKS - 41))
    compute_signals.compute(con)
    assert signals_rows(con, signal_type="decrease") == []


def test_api_decrease_confirmed_on_second_week(con):
    _api_scenario(con, [6_000_000] * 40 + [2_000_000] * (N_WEEKS - 40))
    compute_signals.compute(con)
    rows = signals_rows(con, signal_type="decrease", metric="api_group")
    assert [(r["receptor_uuid"], r["api_group"], r["week"]) for r in rows] == [("rec-a", "Conta", WEEKS[43])]


def test_api_missing_receptor_week_is_not_a_drop(con):
    _api_scenario(con, [2_000_000] * 40 + [None] + [2_000_000] * (N_WEEKS - 41))
    compute_signals.compute(con)
    assert signals_rows(con, metric="api_group") == []


def test_incomplete_api_week_is_blocked_and_recorded(con):
    """Coleta parcial: todo o ecossistema despenca numa semana → trava de cobertura."""
    established(con, "rec-a", "Alvo")
    established(con, "rec-b", "Controle")
    target  = [2_000_000] * N_WEEKS
    control = [50_000_000] * N_WEEKS
    target[45], control[45] = 200_000, 5_000_000
    add_api(con, "rec-a", "Alvo", "accounts", target)
    add_api(con, "rec-b", "Controle", "accounts", control)
    compute_signals.compute(con)

    skipped = json.loads(con.execute("SELECT api_skipped_weeks FROM behavior_signals_run").fetchone()[0])
    assert WEEKS[45] in skipped
    assert signals_rows(con, metric="api_group", week=WEEKS[45]) == []
