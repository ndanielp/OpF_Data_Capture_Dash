"""
v2_metrics.py — Cálculos do Dashboard 2.0 (feature 011).

Funções puras sobre séries semanais em formato largo (índice = semana, colunas =
receptor_uuid). Regras de ritmo, crescimento e Top N: specs/011-dashboard-v2/
research.md (Decisões 5–7) e data-model.md. Só leitura do banco.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd
from cachetools import TTLCache

import config
from services.constants import GROUP_LABELS_V2, SHORT_NAMES
from services.of_analytics import resolve_institution_group

PACE_WINDOW_DAYS = 28        # ritmo: 4 semanas
TREND_TOLERANCE = 0.10       # ↑/↓ quando o ritmo difere mais de 10% do anterior
MULTIPLIER_ABOVE = 3.0       # crescimento acima de +300% vira multiplicador
DEFAULT_PERIOD_DAYS = 364    # período padrão do crescimento: 52 semanas

METRICS: tuple[str, ...] = ("unique_pf", "unique_pj", "active", "api")
_UNIQUE_COLUMN = {"unique_pf": "cpf", "unique_pj": "cnpj"}

_frames: TTLCache = TTLCache(maxsize=32, ttl=600)


class TableMissing(Exception):
    """Tabela da base ainda não gerada (ex.: api_status_weekly antes do compute)."""


# ── Base ──────────────────────────────────────────────────────────────────────

def _db_key() -> tuple[str, float]:
    p = Path(config.DB_PATH)
    return str(p), (p.stat().st_mtime if p.exists() else 0.0)


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute("PRAGMA busy_timeout = 3000")
    return con


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    key = (_db_key(), sql, params)
    if key in _frames:
        return _frames[key]
    con = connect()
    try:
        df = pd.read_sql(sql, con, params=params)
    except (sqlite3.OperationalError, pd.errors.DatabaseError) as e:
        if "no such table" in str(e):
            raise TableMissing(str(e)) from e
        raise
    finally:
        con.close()
    _frames[key] = df
    return df


def short_name(name: str) -> str:
    low = (name or "").lower()
    for key, short in SHORT_NAMES:
        if key in low:
            return short
    return (name or "").title()


def _wide(df: pd.DataFrame) -> pd.DataFrame:
    """(date, uuid, value) → índice Timestamp, colunas uuid, NaN onde não há dado."""
    if df.empty:
        return pd.DataFrame()
    w = df.pivot_table(index="date", columns="uuid", values="value", aggfunc="sum")
    w.index = pd.to_datetime(w.index)
    return w.sort_index().astype(float)


def institutions() -> pd.DataFrame:
    """Receptores com o nome mais recente, nome curto e grupo."""
    df = _query(
        "SELECT receptor_uuid AS uuid, receptor AS name, MAX(date) AS last_date "
        "FROM unique_consents WHERE receptor_uuid <> '' GROUP BY receptor_uuid"
    )
    if df.empty:
        return pd.DataFrame(columns=["uuid", "name", "short", "group"])
    df = df.copy()
    df["short"] = df["name"].map(short_name)
    df["group"] = df["name"].map(resolve_institution_group)
    return df[["uuid", "name", "short", "group"]]


def load_metric(metric: str, status: str = "200") -> pd.DataFrame:
    """Série semanal larga da métrica. API usa api_status_weekly; com status 200 e a
    tabela ainda ausente, cai para api_group_weekly (mesma base de sucesso)."""
    if metric in _UNIQUE_COLUMN:
        col = _UNIQUE_COLUMN[metric]   # whitelist — nunca vem do usuário
        return _wide(_query(
            f"SELECT date, receptor_uuid AS uuid, SUM({col}) AS value FROM unique_consents "
            "WHERE receptor_uuid <> '' GROUP BY date, receptor_uuid"))
    if metric == "unique_total":
        return _wide(_query(
            "SELECT date, receptor_uuid AS uuid, SUM(total) AS value FROM unique_consents "
            "WHERE receptor_uuid <> '' GROUP BY date, receptor_uuid"))
    if metric == "active":
        return _wide(_query(
            "SELECT date, receptor_uuid AS uuid, SUM(total) AS value FROM active_consents "
            "GROUP BY date, receptor_uuid"))
    if metric == "api":
        statuses = {"200": (200,), "500": (500,), "all": (200, 500)}[status]
        ph = ",".join("?" * len(statuses))
        try:
            return _wide(_query(
                f"SELECT date, receptor_uuid AS uuid, SUM(total) AS value FROM api_status_weekly "
                f"WHERE status IN ({ph}) GROUP BY date, receptor_uuid", statuses))
        except TableMissing:
            if status != "200":
                raise
            return _wide(_query(
                "SELECT date, receptor_uuid AS uuid, SUM(req_week) AS value FROM api_group_weekly "
                "GROUP BY date, receptor_uuid"))
    raise ValueError(f"métrica desconhecida: {metric}")


def computed_at() -> str | None:
    try:
        df = _query("SELECT computed_at FROM behavior_signals_run WHERE id = 1")
    except TableMissing:
        return None
    return None if df.empty else str(df.iloc[0, 0])


def collected_at() -> str | None:
    """Data da última coleta (para o cabeçalho); sem registro, a do cálculo de alertas."""
    df = _query("SELECT MAX(fetched_at) AS f FROM unique_consents")
    f = None if df.empty else df.iloc[0, 0]
    return str(f)[:10] if f else (computed_at() or "")[:10] or None


# ── Ritmo e crescimento ───────────────────────────────────────────────────────

def _last_obs(s: pd.Series, at: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    s = s[s.index <= at].dropna()
    return (s.index[-1], float(s.iloc[-1])) if len(s) else None


def _trend(cur: float | None, prev: float | None) -> str:
    if cur is None or prev is None or prev == 0:
        return "flat"
    rel = (cur - prev) / abs(prev)
    if rel > TREND_TOLERANCE:
        return "up"
    if rel < -TREND_TOLERANCE:
        return "down"
    return "flat"


def pace_stock(s: pd.Series, week: pd.Timestamp) -> dict | None:
    """Consentimentos (estoque): ganho por dia entre a semana e 4 semanas antes,
    contra o mesmo cálculo 4 semanas antes. Semana ausente → observação anterior
    mais próxima, dividindo pelos dias reais (nunca compara com zero)."""
    cur = _last_obs(s, week)
    if cur is None or cur[0] != week:
        return None
    base = _last_obs(s, week - pd.Timedelta(days=PACE_WINDOW_DAYS))
    if base is None:
        return None
    days = (week - base[0]).days
    per_day = (cur[1] - base[1]) / days
    pct = (cur[1] / base[1] - 1) / days if base[1] > 0 else None
    prev_base = _last_obs(s, base[0] - pd.Timedelta(days=PACE_WINDOW_DAYS))
    prev = (base[1] - prev_base[1]) / (base[0] - prev_base[0]).days if prev_base else None
    return {"per_day": per_day, "pct_per_day": pct, "prev_per_day": prev, "trend": _trend(per_day, prev)}


def pace_flow(s: pd.Series, week: pd.Timestamp) -> dict | None:
    """Chamadas (fluxo): média diária nas 4 semanas até a semana, contra as 4 anteriores."""
    win = pd.Timedelta(days=PACE_WINDOW_DAYS)
    recent = s[(s.index > week - win) & (s.index <= week)].dropna()
    prior = s[(s.index > week - 2 * win) & (s.index <= week - win)].dropna()
    if recent.empty:
        return None
    per_day = float(recent.mean()) / 7
    prev = float(prior.mean()) / 7 if not prior.empty else None
    pct = per_day / prev - 1 if prev else None
    return {"per_day": per_day, "pct_per_day": None, "prev_per_day": prev,
            "change_pct": pct, "trend": _trend(per_day, prev)}


def _debut(s: pd.Series) -> pd.Timestamp | None:
    pos = s[s > 0].dropna()
    return pos.index[0] if len(pos) else None


def format_growth(ratio: float | None, debut: pd.Timestamp | None, start: pd.Timestamp) -> dict:
    if debut is not None and debut > start:
        return {"kind": "debut", "value": None, "debut_month": debut.strftime("%Y-%m")}
    if ratio is None or math.isnan(ratio) or math.isinf(ratio):
        return {"kind": "no_base", "value": None, "debut_month": None}
    if ratio - 1 > MULTIPLIER_ABOVE:
        return {"kind": "multiplier", "value": ratio, "debut_month": None}
    return {"kind": "pct", "value": ratio - 1, "debut_month": None}


def _period_start(s: pd.Series, start: pd.Timestamp) -> pd.Timestamp:
    """Início efetivo: estar presente na primeira semana da base não é estreia — a
    coleta começou ali, não a operação (mesma regra da feature 010)."""
    return max(start, s.index.min()) if len(s.index) else start


def growth_stock(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Valor na semana final contra a primeira semana do período."""
    start = _period_start(s, start)
    debut = _debut(s)
    first = s[(s.index >= start)].dropna()
    last = _last_obs(s, end)
    if first.empty or last is None or first.iloc[0] <= 0:
        return format_growth(None, debut, start)
    return format_growth(last[1] / float(first.iloc[0]), debut, start)


def growth_flow(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Média das 4 semanas até o fim contra a média das 4 semanas até o início."""
    win = pd.Timedelta(days=PACE_WINDOW_DAYS)
    start = _period_start(s, start)
    debut = _debut(s)
    head = s[(s.index > start - win) & (s.index <= start)].dropna()
    if head.empty:   # período começa na primeira semana da base
        head = s[(s.index >= start) & (s.index < start + win)].dropna()
    tail = s[(s.index > end - win) & (s.index <= end)].dropna()
    if head.empty or tail.empty or head.mean() <= 0:
        return format_growth(None, debut, start)
    return format_growth(float(tail.mean()) / float(head.mean()), debut, start)


def _growth_sort_key(g: dict) -> float:
    if g["kind"] == "pct":
        return g["value"]
    if g["kind"] == "multiplier":
        return g["value"] - 1
    return float("-inf")   # estreia / sem base: fim da lista


# ── Ranking ───────────────────────────────────────────────────────────────────

def build_ranking(
    rows: list[dict],
    *,
    sort: str,
    limit: int,
    pinned: Iterable[str],
    excluded: Iterable[str],
    groups: list[str] | None,
) -> tuple[list[dict], list[dict]]:
    """Top N com fixadas e excluídas (data-model.md, "Linha de ranking").

    rows: uma por instituição, com uuid, group, value, pace, growth e
    per_consent_month. `rank` é a posição no ecossistema inteiro pelo critério
    de ordenação, antes de exclusões e filtro de grupos; fixadas ignoram o filtro
    de grupos; fixadas fora do corte voltam ao fim com below_cut=True.
    """
    pinned, excluded = set(pinned), set(excluded)
    keyf = {
        "total": lambda r: r["value"],
        "pace": lambda r: (r["pace"] or {}).get("per_day") if r["pace"] else float("-inf"),
        "growth": lambda r: _growth_sort_key(r["growth"]),
        "per_consent": lambda r: r["per_consent_month"] if r["per_consent_month"] is not None else float("-inf"),
    }[sort]
    ordered = sorted(rows, key=lambda r: (-(keyf(r) if keyf(r) is not None else float("-inf")), r["name"]))
    for i, r in enumerate(ordered, start=1):
        r["rank"] = i
        r["pinned"] = r["uuid"] in pinned
        r["below_cut"] = False

    candidates = [r for r in ordered if r["uuid"] not in excluded
                  and (groups is None or r["group"] in groups or r["pinned"])]
    top = candidates[:limit]
    in_top = {r["uuid"] for r in top}
    below = [dict(r, below_cut=True) for r in ordered
             if r["pinned"] and r["uuid"] not in in_top and r["uuid"] not in excluded]
    # Só as exclusões que mudam o corte: as que estariam no Top N sem a exclusão.
    excl = [{"uuid": r["uuid"], "name": r["name"], "rank": r["rank"]}
            for r in ordered if r["uuid"] in excluded and r["rank"] <= limit]
    return top + below, excl


def filters_label(groups: list[str] | None, excluded: list[dict]) -> str:
    parts = []
    if groups and set(groups) != set(GROUP_LABELS_V2):
        parts.append("só " + " e ".join(GROUP_LABELS_V2[g] for g in GROUP_LABELS_V2 if g in groups))
    if excluded:
        parts.append("sem " + ", ".join(e["name"] for e in excluded))
    return " · ".join(parts)


# ── Alertas (aba "O que mudou?") ─────────────────────────────────────────────

CONSENT_METRICS = ("unique_consents", "active_consents")
_KIND_ORDER = {"decrease": 0, "increase": 0, "mixed": 0, "oscillation": 1, "new_entrant": 2}


def load_signals() -> pd.DataFrame:
    """behavior_signals com mês, grupo e nome curto. TableMissing se ainda não gerada."""
    df = _query("SELECT week, signal_type, metric, api_group, receptor_uuid, receptor, "
                "value_prev, value_curr, change_pct FROM behavior_signals")
    df = df.copy()
    df["month"] = df["week"].str[:7]
    df["group"] = df["receptor"].map(resolve_institution_group)
    df["short"] = df["receptor"].map(short_name)
    return df


def load_watch() -> pd.DataFrame:
    try:
        df = _query("SELECT week, confirm_week, direction, receptor_uuid, receptor, api_group, "
                    "value_prev, value_curr, change_pct FROM behavior_watch")
    except TableMissing:
        return pd.DataFrame(columns=["week", "confirm_week", "direction", "receptor_uuid", "receptor",
                                     "api_group", "value_prev", "value_curr", "change_pct", "group", "short"])
    df = df.copy()
    df["group"] = df["receptor"].map(resolve_institution_group)
    df["short"] = df["receptor"].map(short_name)
    return df


def month_range(last: str, n: int = 12) -> list[str]:
    end = pd.Period(last, freq="M")
    return [str(end - i) for i in range(n - 1, -1, -1)]


def _oscillation_flags(items: list[dict]) -> list[bool]:
    """Queda seguida de alta (ou o contrário) na mesma métrica de consentimento, em
    semanas consecutivas: os dois alertas formam uma oscilação (research.md, Decisão 9)."""
    flags = [False] * len(items)
    for i, a in enumerate(items):
        for j, b in enumerate(items):
            if (j > i and a["metric"] in CONSENT_METRICS and a["metric"] == b["metric"]
                    and {a["signal_type"], b["signal_type"]} == {"increase", "decrease"}
                    and abs((pd.Timestamp(b["week"]) - pd.Timestamp(a["week"])).days) == 7):
                flags[i] = flags[j] = True
    return flags


def _event_kind(items: list[dict]) -> str:
    rest = {i["signal_type"] for i in items if not i["oscillation"]}
    if not rest:
        return "oscillation"
    if rest == {"new_entrant"}:
        return "new_entrant"
    rest.discard("new_entrant")
    return rest.pop() if len(rest) == 1 else "mixed"


def streak(months_with_alert: set[str], month: str) -> int:
    n, p = 0, pd.Period(month, freq="M")
    while str(p) in months_with_alert:
        n, p = n + 1, p - 1
    return n


def group_events(month_rows: pd.DataFrame, all_rows: pd.DataFrame, month: str,
                 item_fmt) -> list[dict]:
    """Uma entrada por instituição no mês: itens, tipo do evento, maior variação e
    reincidência (meses seguidos com alerta até o mês, com resumo do anterior)."""
    events = []
    prev_month = str(pd.Period(month, freq="M") - 1)
    for uuid, g in month_rows.groupby("receptor_uuid", sort=False):
        g = g.sort_values(["week", "metric", "api_group"])
        items = [item_fmt(r) for r in g.to_dict(orient="records")]
        for it, flag in zip(items, _oscillation_flags(items)):
            it["oscillation"] = flag
        mine = all_rows[all_rows["receptor_uuid"] == uuid]
        n = streak(set(mine["month"]), month)
        prev = mine[mine["month"] == prev_month].sort_values("week")
        changes = [abs(i["change_pct"]) for i in items if i["change_pct"] is not None]
        first = g.iloc[0]
        events.append({
            "uuid": uuid, "name": first["short"], "group": first["group"],
            "kind": _event_kind(items),
            "max_abs_change": max(changes) if changes else None,
            "streak_months": n,
            "items": items,
            "previous_month_summary": [item_fmt(r) for r in prev.to_dict(orient="records")] if n >= 2 else None,
        })
    events.sort(key=lambda e: (_KIND_ORDER.get(e["kind"], 0), -(e["max_abs_change"] or 0), e["name"]))
    return events


def ecosystem_by_group(values: pd.Series, group_of: dict[str, str]) -> list[dict]:
    total = float(values.sum())
    out = []
    for g in GROUP_LABELS_V2:
        v = float(values[[u for u in values.index if group_of.get(u, "outros") == g]].sum())
        out.append({"group": g, "value": v, "share": v / total if total else None})
    return out
