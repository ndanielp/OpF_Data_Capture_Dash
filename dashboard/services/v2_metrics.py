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

import numpy as np
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

# A chave inclui o mtime da base: dado novo invalida sozinho. O TTL longo evita que a
# leitura agregada das tabelas grandes (até ~1 s) volte a cada 10 minutos (Princípio IV).
_frames: TTLCache = TTLCache(maxsize=64, ttl=24 * 3600)


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


def warm() -> None:
    """Pré-carrega as séries compartilhadas pelas abas (chamado em background no startup)."""
    for metric in ("unique_pf", "unique_pj", "unique_total", "active"):
        load_metric(metric)
    for job in (lambda: [load_metric("api", s) for s in ("200", "500", "all")], load_api_groups,
                load_active_by_transmitter, transmitters, institutions, load_signals, load_watch):
        try:
            job()
        except TableMissing:
            pass


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


def flow_means(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[float | None, float | None]:
    """Médias semanais das 4 semanas até o início e das 4 até o fim (base do crescimento
    de fluxos: uma semana isolada não vira base)."""
    win = pd.Timedelta(days=PACE_WINDOW_DAYS)
    start = _period_start(s, start)
    head = s[(s.index > start - win) & (s.index <= start)].dropna()
    if head.empty:   # período começa na primeira semana da base
        head = s[(s.index >= start) & (s.index < start + win)].dropna()
    tail = s[(s.index > end - win) & (s.index <= end)].dropna()
    return (float(head.mean()) if len(head) else None, float(tail.mean()) if len(tail) else None)


def growth_flow(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Média das 4 semanas até o fim contra a média das 4 semanas até o início."""
    head, tail = flow_means(s, start, end)
    start = _period_start(s, start)
    debut = _debut(s)
    if head is None or tail is None or head <= 0:
        return format_growth(None, debut, start)
    return format_growth(tail / head, debut, start)


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


# ── Instituição (aba "Como opera uma instituição?") ──────────────────────────

def ref_members(compare: str, uuid: str, group_of: dict[str, str], universe: Iterable[str]) -> list[str] | None:
    """Quem entra na referência: None = ecossistema inteiro; 'group' = instituições
    do mesmo grupo (soma do grupo); outro UUID = só ela."""
    if compare == "ecosystem":
        return None
    if compare == "group":
        g = group_of.get(uuid, "outros")
        return [u for u in universe if group_of.get(u, "outros") == g]
    return [compare]


def series_of(wide: pd.DataFrame, members: list[str] | None) -> pd.Series:
    """Soma semanal dos membros (None = todos). Semana sem nenhum dado → NaN."""
    if wide.empty:
        return pd.Series(dtype=float)
    cols = wide.columns if members is None else [c for c in members if c in wide.columns]
    if not len(cols):
        return pd.Series(np.nan, index=wide.index)
    return wide[cols].sum(axis=1, min_count=1)


def per_30_days(weekly: pd.Series) -> pd.Series:
    """Fluxo semanal → equivalente a 30 dias pelas últimas 4 semanas (soma ÷ 28 × 30;
    revisão da aba 4 em 2026-10-05). Semana sem dado não entra na média."""
    return weekly.rolling(4, min_periods=1).mean() * 30 / 7


def per_consent_30d(calls_weekly: pd.Series, unique_weekly: pd.Series) -> pd.Series:
    """Chamadas em 30 dias ÷ média de consentimentos únicos (PF + PJ) das mesmas 4 semanas."""
    u = unique_weekly.reindex(calls_weekly.index).rolling(4, min_periods=1).mean()
    return (per_30_days(calls_weekly) / u).where(u > 0)


def paired_sums(calls_wide: pd.DataFrame, unique_wide: pd.DataFrame,
                members: list[str] | None) -> tuple[pd.Series, pd.Series]:
    """Somas de chamadas e de consentimentos únicos de um conjunto (None = todos),
    contando, em cada semana, só os consentimentos de quem teve chamadas naquela
    semana — senão quem não usa API infla o denominador do "por consentimento"."""
    cols = [c for c in (calls_wide.columns if members is None else members)
            if c in calls_wide.columns and c in unique_wide.columns]
    if not cols:
        empty = pd.Series(np.nan, index=calls_wide.index)
        return empty, empty
    c = calls_wide[cols]
    u = unique_wide.reindex(calls_wide.index)[cols].where(c.notna() & (c > 0))
    return c.sum(axis=1, min_count=1), u.sum(axis=1, min_count=1)


def monthly_last(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Último valor de cada mês do período (research.md, Decisão 8): colunas month,
    week, value. Mês sem nenhum dado fica de fora — nunca vira zero."""
    s = s[(s.index >= start) & (s.index <= end)].dropna()
    if s.empty:
        return pd.DataFrame(columns=["month", "week", "value"])
    df = pd.DataFrame({"week": s.index, "value": s.to_numpy()})
    df["month"] = df["week"].dt.strftime("%Y-%m")
    return df.groupby("month", as_index=False).last()[["month", "week", "value"]]


def load_api_groups() -> pd.DataFrame:
    """api_group_weekly longa (status 200): date (Timestamp), uuid, grp, value."""
    df = _query("SELECT date, receptor_uuid AS uuid, grp, SUM(req_week) AS value "
                "FROM api_group_weekly GROUP BY date, receptor_uuid, grp").copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_transmitters(uuid: str) -> pd.DataFrame:
    """Consentimentos ativos da instituição por transmissor (todas as semanas)."""
    df = _query("SELECT date, transmitter_uuid, transmitter, SUM(total) AS value FROM active_consents "
                "WHERE receptor_uuid = ? GROUP BY date, transmitter_uuid", (uuid,)).copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_status_by_transmitter(uuid: str) -> pd.DataFrame:
    """Chamadas da instituição por transmissor e status. TableMissing sem api_status_weekly."""
    df = _query("SELECT date, transmitter_uuid, MAX(transmitter) AS transmitter, status, SUM(total) AS value "
                "FROM api_status_weekly WHERE receptor_uuid = ? GROUP BY date, transmitter_uuid, status",
                (uuid,)).copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── Evolução (aba "Como evolui?") ────────────────────────────────────────────

QUARTER_STABLE = 0.03   # ritmo trimestral "estável" quando a diferença é de até 3 pontos
SNAPSHOT_FILL_WEEKS = 3  # foto de uma semana: lacuna de até 3 semanas usa a observação anterior


def transmitters() -> pd.DataFrame:
    """Transmissores com o nome mais recente, nome curto e grupo (mesmas colunas de institutions)."""
    df = _query("SELECT transmitter_uuid AS uuid, transmitter AS name, MAX(date) AS last_date "
                "FROM active_consents WHERE transmitter_uuid <> '' GROUP BY transmitter_uuid")
    if df.empty:
        return pd.DataFrame(columns=["uuid", "name", "short", "group"])
    df = df.copy()
    df["short"] = df["name"].map(short_name)
    df["group"] = df["name"].map(resolve_institution_group)
    return df[["uuid", "name", "short", "group"]]


def load_active_by_transmitter() -> pd.DataFrame:
    """Consentimentos ativos por transmissor (soma dos receptores), formato largo."""
    return _wide(_query("SELECT date, transmitter_uuid AS uuid, SUM(total) AS value FROM active_consents "
                        "WHERE transmitter_uuid <> '' GROUP BY date, transmitter_uuid"))


def flow_30d(wide: pd.DataFrame) -> pd.DataFrame:
    """Fluxo semanal → equivalente a 30 dias pelas últimas 4 semanas (mesma regra da aba 4),
    mantendo a semana sem coleta como lacuna."""
    return (wide.rolling(4, min_periods=1).mean() * 30 / 7).where(wide.notna())


def by_point(wide: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, granularity: str) -> pd.DataFrame:
    """Matriz ponto × entidade (research.md, Decisão 8). Mensal = último valor de cada
    entidade dentro do mês; semanal = valor da semana. Sem dado → NaN, nunca zero."""
    w = wide[(wide.index >= start) & (wide.index <= end)]
    if granularity == "week":
        out = w.copy()
        out.index = out.index.strftime("%Y-%m-%d")
        return out
    return w.groupby(w.index.strftime("%Y-%m")).last()


def snapshot(wide: pd.DataFrame, at: pd.Timestamp) -> pd.Series:
    """Valores de cada entidade numa semana; lacuna curta usa a observação anterior,
    para a falta de coleta de uma instituição não mexer na participação das outras."""
    w = wide[wide.index <= at]
    if w.empty:
        return pd.Series(dtype=float)
    return w.ffill(limit=SNAPSHOT_FILL_WEEKS).iloc[-1]


def share_changes(wide: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Participação no início e no fim do período e variação em pontos percentuais.
    Quem estreou depois do início parte de zero e leva o mês de estreia."""
    start = max(start, wide.index.min())
    first = wide.index[wide.index >= start].min()
    a, b = snapshot(wide, first).fillna(0), snapshot(wide, end).fillna(0)
    ta, tb = float(a.sum()), float(b.sum())
    df = pd.DataFrame({"share_start": a / ta if ta else np.nan, "share_end": b / tb if tb else np.nan})
    df["pp"] = df["share_end"] - df["share_start"]
    debut = {u: _debut(wide[u]) for u in wide.columns}
    df["debut_month"] = [debut[u].strftime("%Y-%m") if debut[u] is not None and debut[u] > start else None
                         for u in df.index]
    return df


def quarterly_pace(monthly: pd.Series, end_month: str) -> dict | None:
    """Crescimento dos últimos 3 meses contra os 3 anteriores, sobre o valor de fim de mês.
    Sem base em algum dos três pontos → None (quem estreou há menos de 6 meses)."""
    end = pd.Period(end_month, freq="M")
    pts = [str(end - 6), str(end - 3), str(end)]
    v0, v3, v6 = (monthly.get(p) for p in pts)
    if any(v is None or pd.isna(v) for v in (v0, v3, v6)) or v0 <= 0 or v3 <= 0:
        return None
    prev, last = float(v3 / v0 - 1), float(v6 / v3 - 1)
    diff = last - prev
    status = "stable" if abs(diff) <= QUARTER_STABLE + 1e-12 else ("accelerating" if diff > 0 else "decelerating")
    return {"prev_quarter": prev, "last_quarter": last, "status": status, "months": pts}


def ecosystem_by_group(values: pd.Series, group_of: dict[str, str]) -> list[dict]:
    total = float(values.sum())
    out = []
    for g in GROUP_LABELS_V2:
        v = float(values[[u for u in values.index if group_of.get(u, "outros") == g]].sum())
        out.append({"group": g, "value": v, "share": v / total if total else None})
    return out
