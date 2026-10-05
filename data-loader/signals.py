"""
signals.py — Regras de detecção de mudanças de comportamento (feature 010).

As funções detect_* são puras: recebem séries semanais já carregadas e devolvem
alertas. Só as funções load_* e api_coverage tocam o banco.

Todos os limites vivem nas constantes abaixo e foram calibrados contra o histórico
de consents.db (jan/2024 – ago/2026) — ver specs/010-deteccao-mudancas-comportamento/.
"""

from __future__ import annotations

import math
import sqlite3
from typing import NamedTuple

import numpy as np
import pandas as pd

# ── Novo entrante (FR-002) ────────────────────────────────────────────────────
NEW_ENTRANT_FLOOR    = 30_000   # consentimentos únicos
NEW_ENTRANT_GROWTH   = 1.5      # ≥ +50% sobre a base
NEW_ENTRANT_LOOKBACK = 4        # observações da própria série
NEW_WINDOW_WEEKS     = 26       # "novo" = até 26 semanas desde a estreia

# ── Variação de consentimentos (FR-003, FR-004) ───────────────────────────────
CONSENT_FLOOR = 30_000
CONSENT_UP    = 0.20
CONSENT_DOWN  = -0.10

# ── Variação de uso de API (FR-005, FR-006) ───────────────────────────────────
API_WINDOW        = 4            # semanas de cada janela (recente e base)
API_FLOOR         = 1_000_000    # média da base, chamadas/semana
API_UP            = 2.0          # razão relativa ao ecossistema
API_DOWN          = 0.6
API_CONFIRM_WEEKS = 2
API_COVERAGE_MIN  = 0.70         # total da semana vs. mediana das 8 anteriores
API_COVERAGE_LOOKBACK = 8

API_EXCLUDED_GROUPS = ("Resource",)


class Signal(NamedTuple):
    week: str
    signal_type: str          # 'new_entrant' | 'increase' | 'decrease'
    metric: str               # 'unique_consents' | 'active_consents' | 'api_group'
    api_group: str            # '' quando metric não é 'api_group'
    receptor_uuid: str
    receptor: str
    value_prev: float | None
    value_curr: float
    change_pct: float | None
    volume: int


# ── Carga ─────────────────────────────────────────────────────────────────────

def load_consent_series(con: sqlite3.Connection, table: str) -> pd.DataFrame:
    """Série semanal por receptor: colunas date, receptor_uuid, receptor, total.

    active_consents é somada sobre transmissores. `receptor` é o nome mais recente
    do UUID, para o mesmo receptor não aparecer com dois nomes.
    """
    if table not in ("unique_consents", "active_consents"):
        raise ValueError(f"tabela não suportada: {table}")
    df = pd.read_sql(
        f"SELECT date, receptor_uuid, receptor, SUM(total) AS total "
        f"FROM {table} GROUP BY date, receptor_uuid",
        con,
    )
    if df.empty:
        return df
    df = df.sort_values(["receptor_uuid", "date"]).reset_index(drop=True)
    latest_name = df.groupby("receptor_uuid")["receptor"].last()
    df["receptor"] = df["receptor_uuid"].map(latest_name)
    return df


def load_api_pivot(con: sqlite3.Connection) -> tuple[pd.DataFrame, dict[str, str]]:
    """Pivô de api_group_weekly: índice = todas as semanas da tabela (eixo de
    calendário), colunas = (receptor_uuid, grp), valores = req_week.
    Devolve também o nome mais recente de cada receptor."""
    placeholders = ",".join("?" for _ in API_EXCLUDED_GROUPS)
    df = pd.read_sql(
        f"SELECT date, receptor_uuid, receptor, grp, req_week FROM api_group_weekly "
        f"WHERE grp NOT IN ({placeholders})",
        con, params=list(API_EXCLUDED_GROUPS),
    )
    if df.empty:
        return pd.DataFrame(), {}
    df = df.sort_values("date")
    names = df.groupby("receptor_uuid")["receptor"].last().to_dict()
    pivot = df.pivot_table(index="date", columns=["receptor_uuid", "grp"],
                           values="req_week", aggfunc="sum").sort_index()
    return pivot, names


def api_coverage(con: sqlite3.Connection) -> tuple[set[str], list[str]]:
    """Trava de coleta incompleta (research.md, Decisão 3).

    Uma semana só pode ter alerta de API se o total de chamadas do ecossistema for
    ≥ API_COVERAGE_MIN × mediana das semanas anteriores (até API_COVERAGE_LOOKBACK;
    a partir da API_WINDOW-ésima já há mediana e a trava atua). Só as primeiras
    semanas da base, sem mediana, são aprovadas sem checagem — e elas não têm as
    8 semanas que a regra de API exige, então não geram alerta de qualquer forma.
    """
    df = pd.read_sql(
        "SELECT date, SUM(total) AS calls FROM api_requests "
        "WHERE status = 200 AND api <> 'consents' GROUP BY date ORDER BY date",
        con,
    )
    if df.empty:
        return set(), []
    median_prev = (df["calls"]
                   .rolling(API_COVERAGE_LOOKBACK, min_periods=API_WINDOW)
                   .median().shift(1))
    ok = median_prev.isna() | (df["calls"] >= API_COVERAGE_MIN * median_prev)
    approved = set(df.loc[ok, "date"])
    skipped = df.loc[~ok, "date"].tolist()
    return approved, skipped


def first_seen(series: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """Semana de estreia de cada receptor."""
    if series.empty:
        return {}
    return pd.to_datetime(series.groupby("receptor_uuid")["date"].min()).to_dict()


def volume_index(unique: pd.DataFrame) -> dict[tuple[str, str], int]:
    """(receptor_uuid, semana) → consentimentos únicos — usado para ordenar o card."""
    if unique.empty:
        return {}
    return {(u, d): int(t) for u, d, t in
            zip(unique["receptor_uuid"], unique["date"], unique["total"])}


def _num(x: float | None) -> float | None:
    """NaN/None → None, para gravar NULL no SQLite."""
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) else x


def _age_weeks(week: str, debut: pd.Timestamp) -> int:
    return (pd.Timestamp(week) - debut).days // 7


# ── Regras ────────────────────────────────────────────────────────────────────

def detect_new_entrants(unique: pd.DataFrame) -> list[Signal]:
    """FR-002 — receptor recente que estreia ≥ piso, ou cruza o piso crescendo
    ≥ NEW_ENTRANT_GROWTH sobre a observação de NEW_ENTRANT_LOOKBACK posições atrás.

    A janela é por posição na série do próprio receptor (como na calibração): nas
    primeiras semanas a base é a estreia. Quem já estava na primeira semana da
    série não é novo — a coleta começou ali, não a operação.
    """
    if unique.empty:
        return []
    series_start = unique["date"].min()
    out: list[Signal] = []
    for uuid, g in unique.groupby("receptor_uuid", sort=False):
        dates = g["date"].tolist()
        vals = g["total"].tolist()
        if dates[0] == series_start:
            continue
        debut = pd.Timestamp(dates[0])
        for i, (week, v) in enumerate(zip(dates, vals)):
            if _age_weeks(week, debut) > NEW_WINDOW_WEEKS:
                break
            if v < NEW_ENTRANT_FLOOR:
                continue
            base = None if i == 0 else vals[max(0, i - NEW_ENTRANT_LOOKBACK)]
            if base is None or base == 0 or v >= NEW_ENTRANT_GROWTH * base:
                pct = None if not base else v / base - 1
                out.append(Signal(week, "new_entrant", "unique_consents", "", uuid,
                                  g["receptor"].iat[0], _num(base), float(v), _num(pct), int(v)))
                break  # uma vez por receptor
    return out


def detect_consent_changes(
    series: pd.DataFrame,
    metric: str,
    debut_of: dict[str, pd.Timestamp],
    volume_of: dict[tuple[str, str], int],
) -> list[Signal]:
    """FR-003/FR-004 — semana contra a observação anterior do próprio receptor,
    alerta imediato. Só receptores estabelecidos: base ≥ CONSENT_FLOOR e mais de
    NEW_WINDOW_WEEKS de vida (antes disso ele só pode ser novo entrante).

    A idade vem da estreia em consentimentos únicos (`debut_of`), a mesma para as
    duas métricas; na falta dela, da própria série. Semana ausente não vira queda:
    compara-se com a última observação existente, nunca com zero.
    """
    out: list[Signal] = []
    if series.empty:
        return out
    for uuid, g in series.groupby("receptor_uuid", sort=False):
        dates = g["date"].tolist()
        vals = g["total"].tolist()
        debut = debut_of.get(uuid, pd.Timestamp(dates[0]))
        name = g["receptor"].iat[0]
        for i in range(1, len(vals)):
            prev, cur = vals[i - 1], vals[i]
            if prev < CONSENT_FLOOR or _age_weeks(dates[i], debut) <= NEW_WINDOW_WEEKS:
                continue
            pct = cur / prev - 1
            if pct > CONSENT_UP:
                kind = "increase"
            elif pct < CONSENT_DOWN:
                kind = "decrease"
            else:
                continue
            out.append(Signal(dates[i], kind, metric, "", uuid, name, float(prev),
                              float(cur), pct, volume_of.get((uuid, dates[i]), 0)))
    return out


def detect_api_changes(
    pivot: pd.DataFrame,
    approved_weeks: set[str],
    names: dict[str, str],
    volume_of: dict[tuple[str, str], int],
) -> list[Signal]:
    """FR-005/FR-006 — média das API_WINDOW semanas recentes contra as API_WINDOW
    anteriores, dividida pela mesma razão do ecossistema no grupo de API.

    Dividir pelo ecossistema neutraliza feriados e efeitos gerais (Sexta-feira
    Santa derrubou 26% das chamadas de todo mundo). Exigir API_CONFIRM_WEEKS
    semanas seguidas descarta picos isolados; o alerta sai na semana que confirma,
    uma vez por evento. Receptor × semana ausente é NaN, a média móvel também —
    dado faltante nunca vira queda.
    """
    if pivot.empty:
        return []
    w = API_WINDOW
    recent = pivot.rolling(w).mean()
    base = pivot.shift(w).rolling(w).mean()

    grp_total = pivot.T.groupby(level="grp").sum().T
    eco = grp_total.rolling(w).mean() / grp_total.shift(w).rolling(w).mean()
    grps = pivot.columns.get_level_values("grp")
    with np.errstate(divide="ignore", invalid="ignore"):  # base 0/NaN — barrada por `eligible`
        rel = (recent / base).to_numpy() / eco[grps].to_numpy()

    eligible = base.to_numpy() >= API_FLOOR
    approved = pivot.index.isin(list(approved_weeks))[:, None]
    weeks = pivot.index.tolist()
    cols = pivot.columns.tolist()

    out: list[Signal] = []
    for kind, cond in (("increase", rel > API_UP), ("decrease", rel < API_DOWN)):
        hit = pd.DataFrame(cond & eligible & approved)
        confirmed = hit.astype(int).rolling(API_CONFIRM_WEEKS).sum() == API_CONFIRM_WEEKS
        first = (confirmed & ~confirmed.shift(1, fill_value=False)).to_numpy()
        for r, c in zip(*first.nonzero()):
            uuid, grp = cols[c]
            week = weeks[r]
            out.append(Signal(week, kind, "api_group", grp, uuid, names.get(uuid, ""),
                              float(base.iat[r, c]), float(recent.iat[r, c]),
                              float(rel[r, c] - 1), volume_of.get((uuid, week), 0)))
    return out
