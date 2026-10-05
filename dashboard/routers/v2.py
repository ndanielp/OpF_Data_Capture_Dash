"""
v2.py — API do Dashboard 2.0 (feature 011). Contrato: specs/011-dashboard-v2/contracts/v2-api.md

Somente leitura. Tabela ainda não gerada → bloco vazio com `unavailable`, nunca 500
(o dashboard não cria tabelas — Constituição, Princípio V).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from services import v2_metrics as M
from services.constants import API_GROUPS, GROUP_COLORS_V2, GROUP_LABELS_V2, INSTITUTION_GROUP_SLUGS

router = APIRouter()

_SORTS = ("total", "pace", "growth", "per_consent")
_STATUSES = ("200", "500", "all")
_SCALES = ("total", "per_consent")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(obj: Any) -> Any:
    """NaN/inf → None, numpy → Python, para o JSON nunca quebrar."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if hasattr(obj, "item"):          # numpy scalar
        obj = obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _date(s: str | None, field: str) -> pd.Timestamp | None:
    if not s:
        return None
    try:
        return pd.Timestamp(datetime.strptime(s, "%Y-%m-%d"))
    except ValueError:
        raise HTTPException(422, detail=f"Data inválida em '{field}': use AAAA-MM-DD.")


def _list(s: str | None) -> list[str]:
    return [p.strip() for p in (s or "").split(",") if p.strip()]


def _groups(s: str | None) -> list[str] | None:
    """Mesma semântica da feature 009: slug desconhecido é ignorado."""
    parts = [g for g in _list(s) if g in INSTITUTION_GROUP_SLUGS]
    return parts or None


def _choice(value: str, allowed: tuple[str, ...], field: str) -> str:
    if value not in allowed:
        raise HTTPException(422, detail=f"Valor inválido em '{field}': use {', '.join(allowed)}.")
    return value


# ── /meta ─────────────────────────────────────────────────────────────────────

@router.get("/meta")
def meta() -> dict:
    inst = M.institutions()
    try:
        weeks = M.load_metric("unique_total")
        data_through = weeks.index.max().strftime("%Y-%m-%d") if not weeks.empty else None
    except M.TableMissing:
        data_through = None
    return _clean({
        "data_through": data_through,
        "updated_at": M.collected_at(),
        "groups": [{"slug": g, "label": GROUP_LABELS_V2[g], "color": GROUP_COLORS_V2[g]}
                   for g in GROUP_LABELS_V2],
        "api_groups": [{"slug": k, "label": v["display"], "color": v["color"]} for k, v in API_GROUPS.items()],
        "institutions": inst.sort_values("short").to_dict(orient="records"),
    })


# ── /ranking ──────────────────────────────────────────────────────────────────

def _empty_ranking(metric: str, unavailable: list[str]) -> dict:
    return {"metric": metric, "week": None, "period": None, "ecosystem": None,
            "rows": [], "excluded": [], "filters_label": "", "unavailable": unavailable}


@router.get("/ranking")
def ranking(
    metric:   str = Query("unique_pf"),
    start:    Optional[str] = Query(None),
    end:      Optional[str] = Query(None),
    limit:    int = Query(15, ge=1, le=50),
    sort:     str = Query("total"),
    groups:   Optional[str] = Query(None),
    pinned:   Optional[str] = Query(None),
    excluded: Optional[str] = Query(None),
    status:   str = Query("200"),
    scale:    str = Query("total"),
) -> dict:
    metric = _choice(metric, M.METRICS, "metric")
    sort = _choice(sort, _SORTS, "sort")
    status = _choice(status, _STATUSES, "status")
    scale = _choice(scale, _SCALES, "scale")
    is_api = metric == "api"
    if not is_api and (sort == "per_consent" or status != "200" or scale != "total"):
        raise HTTPException(422, detail="'status', 'scale' e sort=per_consent só valem para metric=api.")
    if scale == "per_consent":
        sort = "per_consent"
    start_ts, end_ts = _date(start, "start"), _date(end, "end")

    try:
        wide = M.load_metric(metric, status)
    except M.TableMissing:
        return _empty_ranking(metric, ["errors"])
    if wide.empty:
        return _empty_ranking(metric, [])

    weeks = wide.index[wide.index <= end_ts] if end_ts is not None else wide.index
    if len(weeks) == 0:
        return _empty_ranking(metric, [])
    week = weeks.max()
    start_ts = start_ts if start_ts is not None else week - pd.Timedelta(days=M.DEFAULT_PERIOD_DAYS)
    if start_ts >= week:
        raise HTTPException(422, detail="'start' precisa ser anterior à semana final.")

    inst = M.institutions().set_index("uuid")
    group_of = inst["group"].to_dict()
    short_of = inst["short"].to_dict()

    values = wide.loc[week].dropna()
    values = values[values > 0]
    total = float(values.sum())

    unique_at = pd.Series(dtype=float)
    ok_at = err_at = pd.Series(dtype=float)
    if is_api:
        uniq = M.load_metric("unique_total")
        if week in uniq.index:
            unique_at = uniq.loc[week].dropna()
        if status != "200":
            ok_w, err_w = M.load_metric("api", "200"), M.load_metric("api", "500")
            ok_at = ok_w.loc[week].dropna() if week in ok_w.index else ok_at
            err_at = err_w.loc[week].dropna() if week in err_w.index else err_at

    pace_fn = M.pace_flow if is_api else M.pace_stock
    growth_fn = M.growth_flow if is_api else M.growth_stock

    def per_consent(calls: float, uuid: str) -> float | None:
        u = unique_at.get(uuid)
        return calls * 30 / (u * 7) if is_api and u and u > 0 else None

    def error_rate(uuid: str) -> float | None:
        if not is_api or status == "200":
            return None
        ok, err = ok_at.get(uuid, 0.0), err_at.get(uuid, 0.0)
        return err / (ok + err) if ok + err > 0 else None

    rows = []
    for uuid, v in values.items():
        rows.append({
            "uuid": uuid,
            "name": short_of.get(uuid, uuid),
            "group": group_of.get(uuid, "outros"),
            "value": float(v),
            "share": float(v) / total if total and scale == "total" else None,
            "pace": pace_fn(wide[uuid], week),
            "growth": growth_fn(wide[uuid], start_ts, week),
            "per_consent_month": per_consent(float(v), uuid),
            "error_rate": error_rate(uuid),
        })

    grp = _groups(groups)
    out_rows, excl = M.build_ranking(rows, sort=sort, limit=limit, pinned=_list(pinned),
                                     excluded=_list(excluded), groups=grp)

    eco = wide.sum(axis=1, min_count=1)
    top3 = values.sort_values(ascending=False).head(3).sum() / total if is_api and total else None
    with_unique = [u for u in values.index if unique_at.get(u, 0) > 0]
    eco_per_consent = (float(values[with_unique].sum()) * 30 / (float(unique_at[with_unique].sum()) * 7)
                       if is_api and with_unique else None)
    eco_error = None
    if is_api and status != "200":
        ok_sum, err_sum = float(ok_at.sum()), float(err_at.sum())
        eco_error = err_sum / (ok_sum + err_sum) if ok_sum + err_sum > 0 else None

    return _clean({
        "metric": metric,
        "week": week.strftime("%Y-%m-%d"),
        "period": {"start": start_ts.strftime("%Y-%m-%d"), "end": week.strftime("%Y-%m-%d")},
        "status": status if is_api else None,
        "scale": scale if is_api else None,
        "sort": sort,
        "ecosystem": {
            "total": total,
            "receptors": int(len(values)),
            "by_group": M.ecosystem_by_group(values, group_of),
            "pace": (M.pace_flow if is_api else M.pace_stock)(eco, week),
            "growth": (M.growth_flow if is_api else M.growth_stock)(eco, start_ts, week),
            "per_consent_month": eco_per_consent,
            "error_rate": eco_error,
            "top3_share": top3,
        },
        "rows": out_rows,
        "excluded": excl,
        "filters_label": M.filters_label(grp, excl),
        "unavailable": [],
    })
