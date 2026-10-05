"""
v2.py — API do Dashboard 2.0 (feature 011). Contrato: specs/011-dashboard-v2/contracts/v2-api.md

Somente leitura. Tabela ainda não gerada → bloco vazio com `unavailable`, nunca 500
(o dashboard não cria tabelas — Constituição, Princípio V).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from services import v2_metrics as M
import re
import unicodedata

from services.constants import API_GROUPS, GROUP_COLORS_V2, GROUP_LABELS_V2, INSTITUTION_GROUP_SLUGS
from services.of_analytics import resolve_institution_group as resolve_group

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

    uniq = pd.DataFrame()
    ok_at = err_at = pd.Series(dtype=float)
    if is_api:
        uniq = M.load_metric("unique_total")
        if status != "200":
            ok_w, err_w = M.load_metric("api", "200"), M.load_metric("api", "500")
            ok_at = ok_w.loc[week].dropna() if week in ok_w.index else ok_at
            err_at = err_w.loc[week].dropna() if week in err_w.index else err_at

    pace_fn = M.pace_flow if is_api else M.pace_stock
    growth_fn = M.growth_flow if is_api else M.growth_stock

    def per_consent(calls: pd.Series, unique: pd.Series) -> float | None:
        """Mesma regra da aba 4 (revisão de 2026-10-05): últimas 4 semanas normalizadas
        para 30 dias ÷ média de consentimentos únicos (PF + PJ) das mesmas semanas."""
        if not is_api or unique.empty:
            return None
        v = M.per_consent_30d(calls, unique).get(week)
        return None if v is None or pd.isna(v) else float(v)

    def unique_of(uuid: str) -> pd.Series:
        return uniq[uuid] if uuid in uniq.columns else pd.Series(dtype=float)

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
            "per_consent_month": per_consent(wide[uuid], unique_of(uuid)),
            "error_rate": error_rate(uuid),
        })

    grp = _groups(groups)
    out_rows, excl = M.build_ranking(rows, sort=sort, limit=limit, pinned=_list(pinned),
                                     excluded=_list(excluded), groups=grp)

    eco = wide.sum(axis=1, min_count=1)
    top3 = values.sort_values(ascending=False).head(3).sum() / total if is_api and total else None
    eco_per_consent = per_consent(*M.paired_sums(wide, uniq, None)) if is_api else None
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


# ── /changes ──────────────────────────────────────────────────────────────────

_EVENT_KINDS = ("decrease", "increase", "oscillation", "new_entrant")
_SIGNALS = ("all", "consents", "api")
_METRIC_LABELS = {"unique_consents": "Consentimentos únicos", "active_consents": "Consentimentos ativos"}
_RULES = [
    {"title": "Consentimentos",
     "text": "Semana contra a anterior: queda de 10% ou alta de 20%. Só instituições com "
             "30 mil consentimentos únicos ou mais na semana-base, também para os ativos."},
    {"title": "Uso de API",
     "text": "Média de 4 semanas contra as 4 anteriores, descontado o movimento do ecossistema; "
             "−40% ou +100%, confirmado por 2 semanas seguidas."},
    {"title": "Novo entrante",
     "text": "Passa de 30 mil consentimentos únicos nas primeiras 26 semanas."},
    {"title": "Em observação",
     "text": "Condição de API vista em 1 semana; vira alerta se a semana seguinte confirmar."},
]


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def _api_label(slug: str | None) -> str | None:
    return API_GROUPS.get(slug, {}).get("display", slug) if slug else None


def _item(r: dict) -> dict:
    api = r.get("api_group") or None
    return {
        "week": r["week"], "signal_type": r["signal_type"], "metric": r["metric"],
        "metric_label": _api_label(api) if r["metric"] == "api_group" else _METRIC_LABELS.get(r["metric"], r["metric"]),
        "api_group": api, "api_group_label": _api_label(api),
        "value_prev": r.get("value_prev"), "value_curr": r.get("value_curr"),
        "change_pct": r.get("change_pct"),
    }


def _empty_changes(month: str | None, unavailable: list[str]) -> dict:
    return {"month": month, "months": [], "summary": {"alerts": 0, "institutions": 0, "watching": 0, "by_kind": {}},
            "events": [], "watching": [], "by_group": [], "rules": _RULES, "computed_at": None,
            "unavailable": unavailable}


@router.get("/changes")
def changes(
    month:       Optional[str] = Query(None),
    types:       Optional[str] = Query(None),
    signal:      str = Query("all"),
    institution: Optional[str] = Query(None),
    groups:      Optional[str] = Query(None),
) -> dict:
    if month is not None and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, detail="Mês inválido em 'month': use AAAA-MM.")
    signal = _choice(signal, _SIGNALS, "signal")
    kinds = _list(types) or list(_EVENT_KINDS)
    bad = [k for k in kinds if k not in _EVENT_KINDS]
    if bad:
        raise HTTPException(422, detail=f"Tipo inválido em 'types': use {', '.join(_EVENT_KINDS)}.")

    try:
        sig = M.load_signals()
    except M.TableMissing:
        return _clean(_empty_changes(month, ["signals"]))
    computed = M.computed_at()
    run_through = None
    try:
        run = M._query("SELECT consents_through FROM behavior_signals_run WHERE id = 1")
        run_through = None if run.empty else run.iloc[0, 0]
    except M.TableMissing:
        pass
    last_month = (run_through or (sig["week"].max() if not sig.empty else None) or "")[:7] or None
    if last_month is None:
        return _clean(_empty_changes(month, []))
    month = month or last_month

    grp = _groups(groups)
    q = _norm(institution or "").strip()

    def keep(df: pd.DataFrame) -> pd.DataFrame:
        if signal == "consents":
            df = df[df["metric"].isin(M.CONSENT_METRICS)]
        elif signal == "api":
            df = df[df["metric"] == "api_group"]
        if grp:
            df = df[df["group"].isin(grp)]
        if q:
            df = df[df["short"].map(_norm).str.contains(q, regex=False) | df["receptor"].map(_norm).str.contains(q, regex=False)]
        return df

    filtered = keep(sig)

    def events_of(m: str) -> list[dict]:
        evs = M.group_events(filtered[filtered["month"] == m], sig, m, _item)
        return [e for e in evs if e["kind"] in kinds or (e["kind"] == "mixed" and {"decrease", "increase"} & set(kinds))]

    events = events_of(month)
    # Barra de meses: só os alertas do tipo escolhido (oscilação conta seus 2 alertas).
    def counted(i: dict) -> bool:
        if not _list(types):
            return True
        return "oscillation" in kinds if i["oscillation"] else i["signal_type"] in kinds

    months = []
    for m in M.month_range(last_month):
        items = [i for e in (events if m == month else events_of(m)) for i in e["items"] if counted(i)]
        months.append({"month": m, **{k: sum(1 for i in items if i["signal_type"] == k)
                                       for k in ("decrease", "increase", "new_entrant")}})

    watch = M.load_watch()
    if not watch.empty and signal != "consents":
        if grp:
            watch = watch[watch["group"].isin(grp)]
        if q:
            watch = watch[watch["short"].map(_norm).str.contains(q, regex=False)]
    else:
        watch = watch.iloc[0:0]
    watching = [{"uuid": w["receptor_uuid"], "name": w["short"], "group": w["group"],
                 "direction": w["direction"], "api_group": w["api_group"], "api_group_label": _api_label(w["api_group"]),
                 "value_prev": w["value_prev"], "value_curr": w["value_curr"], "change_pct": w["change_pct"],
                 "week": w["week"], "confirm_week": w["confirm_week"]}
                for w in watch.sort_values("change_pct").to_dict(orient="records")]

    by_kind: dict[str, int] = {}
    for e in events:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    by_group = []
    for g in GROUP_LABELS_V2:
        evs = [e for e in events if e["group"] == g]
        if evs:
            by_group.append({"group": g, "alerts": sum(len(e["items"]) for e in evs), "institutions": len(evs)})

    return _clean({
        "month": month,
        "months": months,
        "summary": {"alerts": sum(len(e["items"]) for e in events), "institutions": len(events),
                    "watching": len(watching), "by_kind": by_kind},
        "events": events,
        "watching": watching,
        "by_group": by_group,
        "rules": _RULES,
        "computed_at": computed,
        "unavailable": [],
    })


# ── /institution/{uuid} ───────────────────────────────────────────────────────
# Regras revisadas com o responsável do produto em 2026-10-05 (spec, Clarifications):
# fluxos de API normalizados para 30 dias pelas últimas 4 semanas; evolução com
# seletor de métrica; mix e grupos na mesma unidade; transmissores com "Outros" e
# crescimento; taxa de erro sobre 4 semanas e todos os meses; alertas como na aba 3.

_TOP_TRANSMITTERS = 8
_EVOLUTION_METRICS = ("unique_total", "unique_pf", "unique_pj", "active", "api", "api_per_consent")


def _last_le(index: pd.Index, at: pd.Timestamp) -> pd.Timestamp | None:
    ok = index[index <= at]
    return ok.max() if len(ok) else None


def _monthly(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[list[str], list[float], list]:
    mm = M.monthly_last(s, start, end)
    return mm["month"].tolist(), mm["value"].tolist(), mm["week"].tolist()


@router.get("/institution/{uuid}")
def institution(
    uuid:    str,
    compare: str = Query("ecosystem"),
    start:   Optional[str] = Query(None),
    end:     Optional[str] = Query(None),
) -> dict:
    inst = M.institutions().set_index("uuid")
    if uuid not in inst.index:
        raise HTTPException(404, detail="Instituição não encontrada nesta base.")
    if compare not in ("ecosystem", "group") and (compare not in inst.index or compare == uuid):
        raise HTTPException(422, detail="'compare' deve ser ecosystem, group ou o identificador de outra instituição.")
    group_of, short_of = inst["group"].to_dict(), inst["short"].to_dict()
    me_group = group_of.get(uuid, "outros")
    start_ts, end_ts = _date(start, "start"), _date(end, "end")

    wides = {m: M.load_metric(m) for m in ("unique_pf", "unique_pj", "active", "api", "unique_total")}
    week = _last_le(wides["unique_total"].index, end_ts) if end_ts is not None else wides["unique_total"].index.max()
    if week is None:
        raise HTTPException(404, detail="Sem dados para o período escolhido.")
    start_ts = start_ts if start_ts is not None else week - pd.Timedelta(days=M.DEFAULT_PERIOD_DAYS)
    if start_ts >= week:
        raise HTTPException(422, detail="'start' precisa ser anterior à semana final.")

    members = M.ref_members(compare, uuid, group_of, inst.index)
    is_other = compare not in ("ecosystem", "group")
    ref_label = {"ecosystem": "Ecossistema", "group": GROUP_LABELS_V2.get(me_group, me_group) + " (grupo)"}.get(
        compare, short_of.get(compare, compare))
    mine = lambda wide: wide[uuid] if uuid in wide.columns else pd.Series(np.nan, index=wide.index)  # noqa: E731
    ref = lambda wide: M.series_of(wide, members)                                                   # noqa: E731
    calls, uniq = wides["api"], wides["unique_total"]
    # Por consentimento: a referência só conta, em cada semana, quem teve chamadas (mesma base da aba 1).
    ref_c, ref_u = M.paired_sums(calls, uniq, members)

    # ── Indicadores ──────────────────────────────────────────────────────────
    def kpi(metric: str) -> dict | None:
        wide = wides[metric]
        flow = metric == "api"
        w = _last_le(wide.index, week) if not wide.empty else None
        if w is None or uuid not in wide.columns or pd.isna(wide.at[w, uuid]):
            return None
        vals = wide.loc[w].dropna()
        vals = vals[vals > 0]
        v = float(wide.at[w, uuid])
        grow = M.growth_flow if flow else M.growth_stock
        pace = M.pace_flow if flow else M.pace_stock
        out = {"value": v, "share": v / float(vals.sum()) if vals.sum() else None,
               "rank": int((vals > v).sum()) + 1, "week": w.strftime("%Y-%m-%d"),
               "growth": grow(wide[uuid], start_ts, w), "ref_growth": grow(ref(wide), start_ts, w),
               "pace": pace(wide[uuid], w)}
        if flow:
            pc, rpc = M.per_consent_30d(mine(calls), mine(uniq)), M.per_consent_30d(ref_c, ref_u)
            out["per_consent_month"] = pc.get(w)
            out["ref_per_consent_month"] = rpc.get(w)
        return out

    kpis = {m: kpi(m) for m in ("unique_pf", "unique_pj", "active", "api")}
    total_kpi = kpi("unique_total")

    # ── Evolução: seletor de métrica (padrão PF + PJ) ────────────────────────
    eco_calls30 = M.per_30_days(calls.sum(axis=1, min_count=1))
    evolution: dict[str, dict] = {}
    for key in _EVOLUTION_METRICS:
        if key == "api_per_consent":
            s_me, s_ref, eco = M.per_consent_30d(mine(calls), mine(uniq)), M.per_consent_30d(ref_c, ref_u), None
        elif key == "api":
            s_me, s_ref, eco = M.per_30_days(mine(calls)), M.per_30_days(ref(calls)), eco_calls30
        else:
            wide = wides[key]
            s_me, s_ref, eco = mine(wide), ref(wide), wide.sum(axis=1, min_count=1)
        pts, vals, wks = _monthly(s_me, start_ts, week)
        rpts, rvals, rwks = _monthly(s_ref, start_ts, week)
        share = (lambda ws, vs: [v / eco.get(w) if eco is not None and eco.get(w) else None for w, v in zip(ws, vs)])
        evolution[key] = {
            "points": pts, "values": vals, "shares": share(wks, vals),
            # Linha de referência: razões estão na mesma escala; contagens, só contra outra instituição.
            "ref": ({"label": ref_label, "points": rpts, "values": rvals, "shares": share(rwks, rvals)}
                    if key == "api_per_consent" or is_other else None),
        }

    # ── Mix de API e chamadas por grupo (sem Resource), últimas 4 semanas → 30 dias ──
    groups_long = M.load_api_groups()
    groups_long = groups_long[groups_long["grp"] != "Resource"]
    api_mix, api_by_group = [], []
    if not groups_long.empty:
        pv = groups_long.pivot_table(index="date", columns=["uuid", "grp"], values="value", aggfunc="sum").sort_index()
        uniq_idx = uniq.reindex(pv.index)
        u_me, u_ref = mine(uniq_idx), ref_u.reindex(pv.index)

        def grp_series(slug: str, who: list[str] | None) -> pd.Series:
            cols = [c for c in pv.columns if c[1] == slug and (who is None or c[0] in who)]
            return pv[cols].sum(axis=1, min_count=1) if cols else pd.Series(np.nan, index=pv.index)

        wk = _last_le(pv.index, week)
        num = lambda s: 0.0 if pd.isna(s.get(wk)) else float(s.get(wk))   # noqa: E731 — NaN não pode virar total
        slugs = [s for s in API_GROUPS if s != "Resource"]
        me30 = {s: M.per_30_days(grp_series(s, [uuid])) for s in slugs}
        ref30 = {s: M.per_30_days(grp_series(s, members)) for s in slugs}
        tot_me = sum(num(me30[s]) for s in slugs)
        tot_ref = sum(num(ref30[s]) for s in slugs)
        u_me_avg = u_me.rolling(4, min_periods=1).mean()
        u_ref_avg = u_ref.rolling(4, min_periods=1).mean()
        for slug in slugs:
            meta_g = API_GROUPS[slug]
            c_me, c_ref = num(me30[slug]), num(ref30[slug])
            share = c_me / tot_me if tot_me else None
            ref_share = c_ref / tot_ref if tot_ref else None
            if max(share or 0, ref_share or 0) >= 0.0005:   # some com 0,0% dos dois lados (ex.: Câmbio)
                um, ur = num(u_me_avg), num(u_ref_avg)
                api_mix.append({
                    "api_group": slug, "label": meta_g["display"], "color": meta_g["color"],
                    "share": share, "ref_share": ref_share,
                    "calls_30d": c_me, "ref_calls_30d": c_ref,
                    "per_consent": c_me / um if um else None,
                    "ref_per_consent": c_ref / ur if ur else None,
                })
            # Tendência no período na mesma unidade do mix.
            tot_series = sum(me30[s].fillna(0) for s in slugs)
            series = {
                "total": me30[slug],
                "per_consent": (me30[slug] / u_me_avg).where(u_me_avg > 0),
                "share": (me30[slug] / tot_series).where(tot_series > 0),
            }
            if M.monthly_last(series["total"], start_ts, week)["value"].sum() <= 0:
                continue
            units = {}
            for unit, s in series.items():
                pts, vals, _ = _monthly(s, start_ts, week)
                if not vals:
                    continue
                frm, to = vals[0], vals[-1]
                growth = ({"kind": "pp", "value": to - frm, "debut_month": None} if unit == "share"
                          else M.format_growth(to / frm if frm and frm > 0 else None, M._debut(s), max(start_ts, s.index.min())))
                units[unit] = {"points": pts, "monthly": vals, "from": frm, "to": to, "growth": growth}
            api_by_group.append({"api_group": slug, "label": meta_g["display"], "color": meta_g["color"], "units": units})

    # ── Transmissores: top 8 + Outros, com crescimento no período ────────────
    tx = M.load_transmitters(uuid)
    transmitters: list[dict] = []
    if not tx.empty:
        wt = _last_le(pd.Index(tx["date"].unique()), week)
        at = tx[tx["date"] == wt].sort_values("value", ascending=False)
        tot = float(at["value"].sum())
        series_tx = tx.pivot_table(index="date", columns="transmitter_uuid", values="value", aggfunc="sum").sort_index()
        for r in at.head(_TOP_TRANSMITTERS).to_dict(orient="records"):
            transmitters.append({"name": M.short_name(r["transmitter"]), "group": resolve_group(r["transmitter"]),
                                 "value": r["value"], "share": r["value"] / tot if tot else None,
                                 "growth": M.growth_stock(series_tx[r["transmitter_uuid"]], start_ts, wt)})
        rest = at.iloc[_TOP_TRANSMITTERS:]
        if len(rest):
            v = float(rest["value"].sum())
            transmitters.append({"name": f"Outros ({len(rest)} transmissores)", "group": None, "other": True,
                                 "value": v, "share": v / tot if tot else None, "growth": None})

    # ── Taxa de erro: últimas 4 semanas e todos os meses ─────────────────────
    unavailable: list[str] = []
    error_rate = None
    try:
        st_long = M.load_status_by_transmitter(uuid)
        ok_w, err_w = M.load_metric("api", "200"), M.load_metric("api", "500")

        def window(df_or_s, until: pd.Timestamp):
            idx = df_or_s.index if isinstance(df_or_s, pd.Series) else pd.Index(df_or_s["date"])
            return (idx > until - pd.Timedelta(days=M.PACE_WINDOW_DAYS)) & (idx <= until)

        def rate(err: float, ok: float) -> float | None:
            return err / (err + ok) if err + ok > 0 else None

        me_ok = st_long[st_long["status"] == 200].groupby("date")["value"].sum()
        me_err = st_long[st_long["status"] == 500].groupby("date")["value"].sum()
        rf_ok, rf_err = ref(ok_w), ref(err_w)
        ws = _last_le(pd.Index(st_long["date"].unique()), week) if not st_long.empty else None
        cur = ref_cur = None
        by_tx: list[dict] = []
        if ws is not None:
            cur = rate(float(me_err[window(me_err, ws)].sum()), float(me_ok[window(me_ok, ws)].sum()))
            ref_cur = rate(float(rf_err[window(rf_err, ws)].sum()), float(rf_ok[window(rf_ok, ws)].sum()))
            last4 = st_long[window(st_long, ws)].pivot_table(index=["transmitter_uuid", "transmitter"], columns="status",
                                                              values="value", aggfunc="sum").fillna(0)
            last4["vol"] = last4.sum(axis=1)
            for (_tu, name), r in last4.sort_values("vol", ascending=False).head(_TOP_TRANSMITTERS).iterrows():
                by_tx.append({"name": M.short_name(name), "value": rate(float(r.get(500, 0)), float(r.get(200, 0))),
                              "volume": float(r["vol"])})
            by_tx.sort(key=lambda x: -(x["value"] or 0))

        def by_month(err: pd.Series, ok: pd.Series) -> dict[str, float | None]:
            e = err[(err.index >= start_ts) & (err.index <= week)].groupby(err.index[(err.index >= start_ts) & (err.index <= week)].strftime("%Y-%m")).sum()
            o = ok[(ok.index >= start_ts) & (ok.index <= week)].groupby(ok.index[(ok.index >= start_ts) & (ok.index <= week)].strftime("%Y-%m")).sum()
            return {m: rate(float(e.get(m, 0)), float(o.get(m, 0))) for m in sorted(set(e.index) | set(o.index))}

        mm_me, mm_ref = by_month(me_err, me_ok), by_month(rf_err.fillna(0), rf_ok.fillna(0))
        error_rate = {
            "current": cur, "ref_current": ref_cur,
            "week": ws.strftime("%Y-%m-%d") if ws is not None else None,
            "series": [{"point": m, "value": v, "ref": mm_ref.get(m)} for m, v in mm_me.items()],
            "by_transmitter": by_tx,
        }
    except M.TableMissing:
        unavailable.append("errors")

    # ── Alertas: como na aba 3 (eventos por mês, oscilação, em observação) ──
    alerts = {"events": [], "watching": [], "last_alert": None}
    try:
        sig = M.load_signals()
        mine_sig = sig[sig["receptor_uuid"] == uuid]
        cutoff = (week - pd.Timedelta(days=M.DEFAULT_PERIOD_DAYS)).strftime("%Y-%m-%d")
        recent = mine_sig[mine_sig["week"] >= cutoff]
        for m in sorted(recent["month"].unique(), reverse=True):
            for e in M.group_events(recent[recent["month"] == m], sig, m, _item):
                alerts["events"].append(dict(e, month=m))
        if recent.empty and not mine_sig.empty:
            lw = mine_sig["week"].max()
            same = mine_sig[mine_sig["week"] == lw]
            alerts["last_alert"] = {"week": lw, "items": [_item(r) for r in same.to_dict(orient="records")]}
        watch = M.load_watch()
        alerts["watching"] = [{"api_group": w["api_group"], "api_group_label": _api_label(w["api_group"]),
                               "direction": w["direction"], "value_prev": w["value_prev"], "value_curr": w["value_curr"],
                               "change_pct": w["change_pct"], "week": w["week"], "confirm_week": w["confirm_week"]}
                              for w in watch[watch["receptor_uuid"] == uuid].to_dict(orient="records")]
    except M.TableMissing:
        unavailable.append("signals")

    return _clean({
        "institution": {"uuid": uuid, "name": short_of.get(uuid, uuid), "group": me_group,
                        "ranks": {m: (k or {}).get("rank") for m, k in kpis.items()}},
        "week": week.strftime("%Y-%m-%d"),
        "period": {"start": start_ts.strftime("%Y-%m-%d"), "end": week.strftime("%Y-%m-%d")},
        "compare": {"kind": "institution" if is_other else compare,
                    "uuid": compare if is_other else None, "label": ref_label},
        "kpis": kpis,
        "unique_total_share": (total_kpi or {}).get("share"),
        "evolution": evolution,
        "api_mix": api_mix,
        "api_by_group": api_by_group,
        "transmitters": transmitters,
        "error_rate": error_rate,
        "alerts": alerts,
        "unavailable": unavailable,
    })


# ── /evolution ────────────────────────────────────────────────────────────────
# Aba "Como evolui?": tendência do período (research.md, Decisão 8). Fluxos de API
# em 30 dias pelas últimas 4 semanas, como na aba 4; contagens como estão.

_GRANULARITIES = ("month", "week")
_BY = ("receptor", "transmitter")
_MAX_LINES = 8
_DEFAULT_LINES = 5
_CHANGES_EACH_SIDE = 5
_PACE_TOP = 10


def _empty_evolution(metric: str, granularity: str, by: str, unavailable: list[str]) -> dict:
    return {"metric": metric, "granularity": granularity, "by": by, "week": None, "period": None,
            "points": [], "headline": None, "series": [], "group_share": [], "group_share_change": [],
            "share_changes": [], "quarterly_pace": [], "ecosystem_quarterly_pace": None,
            "filters_label": "", "unavailable": unavailable}


@router.get("/evolution")
def evolution(
    metric:       str = Query("unique_pf"),
    granularity:  str = Query("month"),
    institutions: Optional[str] = Query(None),
    by:           str = Query("receptor"),
    start:        Optional[str] = Query(None),
    end:          Optional[str] = Query(None),
    groups:       Optional[str] = Query(None),
) -> dict:
    metric = _choice(metric, M.METRICS, "metric")
    granularity = _choice(granularity, _GRANULARITIES, "granularity")
    by = _choice(by, _BY, "by")
    if by == "transmitter" and metric != "active":
        raise HTTPException(422, detail="'by=transmitter' só vale para metric=active.")
    ids = list(dict.fromkeys(_list(institutions)))
    if len(ids) > _MAX_LINES:
        raise HTTPException(422, detail=f"Escolha até {_MAX_LINES} instituições.")
    start_ts, end_ts = _date(start, "start"), _date(end, "end")

    try:
        raw = M.load_active_by_transmitter() if by == "transmitter" else M.load_metric(metric)
    except M.TableMissing:
        return _clean(_empty_evolution(metric, granularity, by, ["data"]))
    if raw.empty:
        return _clean(_empty_evolution(metric, granularity, by, []))
    week = _last_le(raw.index, end_ts) if end_ts is not None else raw.index.max()
    if week is None:
        return _clean(_empty_evolution(metric, granularity, by, []))
    start_ts = start_ts if start_ts is not None else week - pd.Timedelta(days=M.DEFAULT_PERIOD_DAYS)
    if start_ts >= week:
        raise HTTPException(422, detail="'start' precisa ser anterior à semana final.")

    ents = (M.transmitters() if by == "transmitter" else M.institutions()).set_index("uuid")
    group_of, short_of = ents["group"].to_dict(), ents["short"].to_dict()
    grp = _groups(groups)
    in_groups = lambda u: grp is None or group_of.get(u, "outros") in grp   # noqa: E731

    is_flow = metric == "api"
    vals = M.flow_30d(raw) if is_flow else raw
    growth_fn = M.growth_flow if is_flow else M.growth_stock
    growth_of = lambda u: growth_fn(raw[u], start_ts, week)                 # noqa: E731

    # ── Respostas do topo e ganhos/perdas de participação (sempre sobre o total) ──
    eco_raw = raw.sum(axis=1, min_count=1)
    eco_growth = growth_fn(eco_raw, start_ts, week)
    if is_flow:
        head, tail = M.flow_means(eco_raw, start_ts, week)
        eco_from = head * 30 / 7 if head is not None else None
        eco_to = tail * 30 / 7 if tail is not None else None
    else:
        first = eco_raw[eco_raw.index >= M._period_start(eco_raw, start_ts)].dropna()
        eco_from = float(first.iloc[0]) if len(first) else None
        eco_to = float(eco_raw[week]) if pd.notna(eco_raw.get(week)) else None

    sc = M.share_changes(vals, start_ts, week)
    sc = sc[sc["pp"].notna() & np.array([in_groups(u) for u in sc.index], dtype=bool)]
    end_snap = M.snapshot(vals, week)

    def change_row(u: str) -> dict:
        r = sc.loc[u]
        return {"uuid": u, "name": short_of.get(u, u), "group": group_of.get(u, "outros"),
                "pp": float(r["pp"]) * 100, "share": float(r["share_end"]), "share_start": float(r["share_start"]),
                "debut_month": r["debut_month"], "growth": growth_of(u)}

    ordered = sc.sort_values("pp", ascending=False)
    gainers = [u for u in ordered.index if ordered.at[u, "pp"] > 0][:_CHANGES_EACH_SIDE]
    losers = [u for u in reversed(ordered.index) if ordered.at[u, "pp"] < 0][:_CHANGES_EACH_SIDE]
    share_changes = [change_row(u) for u in gainers] + [change_row(u) for u in reversed(losers)]
    headline = {
        "ecosystem_growth": dict(eco_growth, **{"from": eco_from, "to": eco_to}),
        "top_gainer": change_row(gainers[0]) if gainers else None,
        "top_loser": change_row(losers[0]) if losers else None,
    }

    # ── Linhas do gráfico: as escolhidas ou as 5 maiores no fim do período ──
    matrix = M.by_point(vals, start_ts, week, granularity)
    total = matrix.sum(axis=1, min_count=1)
    ids = [u for u in ids if u in matrix.columns]
    if not ids:
        ranked = end_snap.dropna().sort_values(ascending=False)
        ids = [u for u in ranked.index if in_groups(u)][:_DEFAULT_LINES]
    series = []
    for u in ids:
        col = matrix[u]
        last = col.dropna()
        series.append({
            "uuid": u, "name": short_of.get(u, u), "group": group_of.get(u, "outros"),
            "values": col.tolist(), "shares": (col / total).tolist(),
            "last": float(last.iloc[-1]) if len(last) else None,
            "growth": growth_of(u),
        })

    # ── Participação por grupo, mês a mês ────────────────────────────────────
    monthly = matrix if granularity == "month" else M.by_point(vals, start_ts, week, "month")
    m_total = monthly.sum(axis=1, min_count=1)
    by_grp = {g: monthly[[u for u in monthly.columns if group_of.get(u, "outros") == g]].sum(axis=1)
              for g in GROUP_LABELS_V2}
    group_share = [{"point": p, **{g: (float(by_grp[g][p]) / float(m_total[p]) if m_total[p] else None)
                                   for g in GROUP_LABELS_V2}} for p in monthly.index]
    group_share_change = []
    if group_share:
        a_row, b_row = group_share[0], group_share[-1]
        for g in GROUP_LABELS_V2:
            a, b = a_row[g], b_row[g]
            group_share_change.append({"group": g, "share": b,
                                       "pp": (b - a) * 100 if a is not None and b is not None else None})

    # ── Ritmo trimestral: 10 maiores no fim (nos grupos escolhidos) e ecossistema ──
    end_month = week.strftime("%Y-%m")
    full_monthly = M.by_point(vals, vals.index.min(), week, "month")
    top = [u for u in end_snap.dropna().sort_values(ascending=False).index if in_groups(u)][:_PACE_TOP]
    pace_rows = []
    for u in top:
        qp = M.quarterly_pace(full_monthly[u], end_month)
        if qp:
            pace_rows.append({"uuid": u, "name": short_of.get(u, u), "group": group_of.get(u, "outros"), **qp})
    pace_rows.sort(key=lambda r: -(r["last_quarter"] - r["prev_quarter"]))
    eco_vals = M.flow_30d(eco_raw.to_frame("eco")) if is_flow else eco_raw.to_frame("eco")
    eco_pace = M.quarterly_pace(M.by_point(eco_vals, eco_vals.index.min(), week, "month")["eco"], end_month)

    return _clean({
        "metric": metric, "granularity": granularity, "by": by,
        "week": week.strftime("%Y-%m-%d"),
        "period": {"start": start_ts.strftime("%Y-%m-%d"), "end": week.strftime("%Y-%m-%d")},
        "points": matrix.index.tolist(),
        "headline": headline,
        "series": series,
        "group_share": group_share,
        "group_share_change": group_share_change,
        "share_changes": share_changes,
        "quarterly_pace": pace_rows,
        "ecosystem_quarterly_pace": eco_pace,
        "filters_label": M.filters_label(grp, []),
        # Busca de transmissores no "+ Adicionar" (o /meta só lista receptores).
        "catalog": (ents.reset_index()[["uuid", "name", "short", "group"]].sort_values("short").to_dict(orient="records")
                    if by == "transmitter" else None),
        "unavailable": [],
    })
