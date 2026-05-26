"""
active_consents.py — FastAPI router para as visões de Consentimentos Ativos.

Endpoints:
  GET /api/active-consents/evolution  — série temporal por receptor ou transmissor
  GET /api/active-consents/matrix     — heatmap receptor × transmissor (semana mais recente)
  GET /api/active-consents/ranking    — top-N por volume + Δ% semanal
  GET /api/active-consents/intensity  — intensidade de uso (ativos ÷ únicos) por receptor
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import config
from services.constants import BRAND_COLORS

router = APIRouter()

# ── Fallback colors (mesma lista de server.py) ────────────────────────────────
_FALLBACK_COLORS: list[str] = [
    "#4A9EFF", "#7B68EE", "#FF5722", "#34B7F1",
    "#9C27B0", "#F9E68C", "#cba6f7", "#f38ba8",
    "#fab387", "#94e2d5", "#b4befe", "#a6e3a1",
]


# ── Helpers privados ──────────────────────────────────────────────────────────

def _db_con() -> sqlite3.Connection:
    """Abre conexão SQLite read-only com PRAGMAs de performance."""
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute("PRAGMA cache_size = -4096")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA mmap_size = 268435456")
    con.execute("PRAGMA temp_store = MEMORY")
    con.execute("PRAGMA busy_timeout = 3000")
    return con


def _brand_color(name: str) -> str | None:
    n = name.lower()
    for key, color in BRAND_COLORS:
        if key in n:
            return color
    return None


def _build_color_map(names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    fb_idx = 0
    for name in names:
        c = _brand_color(name)
        if c:
            result[name] = c
            used.add(c)
        else:
            while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                fb_idx += 1
            c = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
            used.add(c)
            fb_idx += 1
            result[name] = c
    return result


def _parse_date(s: str | None, fallback: date) -> date:
    if not s:
        return fallback
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback


def _parse_receptors(receptors_param: str | None) -> list[str] | None:
    if not receptors_param:
        return None
    parts = [r.strip() for r in receptors_param.split(",") if r.strip()]
    return parts if parts else None


def _latest_date_in_table(con: sqlite3.Connection, before: str) -> str | None:
    """Retorna a data mais recente em active_consents <= before."""
    row = con.execute(
        "SELECT MAX(date) FROM active_consents WHERE date <= ?", (before,)
    ).fetchone()
    return row[0] if row and row[0] else None


def _prev_date_in_table(con: sqlite3.Connection, before: str) -> str | None:
    """Retorna a data imediatamente anterior a 'before' em active_consents."""
    row = con.execute(
        "SELECT MAX(date) FROM active_consents WHERE date < ?", (before,)
    ).fetchone()
    return row[0] if row and row[0] else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/evolution")
def evolution(
    start: Optional[str] = Query(None),
    end:   Optional[str] = Query(None),
    by:    str            = Query("receptor", pattern="^(receptor|transmitter)$"),
    receptors: Optional[str] = Query(None),
) -> JSONResponse:
    """Série temporal de consentimentos ativos agrupada por receptor ou transmissor."""
    today    = date.today()
    dt_start = _parse_date(start, today - timedelta(weeks=52))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)

    dim_col = "receptor" if by == "receptor" else "transmitter"

    try:
        con = _db_con()
        try:
            if sel:
                # Filtro por substring nos nomes de receptor
                placeholders = " OR ".join(["receptor LIKE ?" for _ in sel])
                params: list = [f"%{r}%" for r in sel]
                params = [dt_start.isoformat(), dt_end.isoformat()] + params
                rows = con.execute(
                    f"SELECT {dim_col}, date, SUM(total) AS total "
                    f"FROM active_consents "
                    f"WHERE date BETWEEN ? AND ? AND ({placeholders}) "
                    f"GROUP BY {dim_col}, date "
                    f"ORDER BY date, total DESC",
                    params,
                ).fetchall()
            else:
                rows = con.execute(
                    f"SELECT {dim_col}, date, SUM(total) AS total "
                    f"FROM active_consents "
                    f"WHERE date BETWEEN ? AND ? "
                    f"GROUP BY {dim_col}, date "
                    f"ORDER BY date, total DESC",
                    (dt_start.isoformat(), dt_end.isoformat()),
                ).fetchall()
        finally:
            con.close()
    except Exception:
        return JSONResponse({"labels": [], "series": [], "by": by})

    if not rows:
        return JSONResponse({"labels": [], "series": [], "by": by})

    # Agrupa por dimensão → {name: {date: total}}
    series_data: dict[str, dict[str, int]] = {}
    all_dates: set[str] = set()
    for dim, dt, total in rows:
        series_data.setdefault(dim, {})[dt] = total
        all_dates.add(dt)

    sorted_dates = sorted(all_dates)
    names = list(series_data.keys())
    colors = _build_color_map(names)

    series = [
        {
            "name":   name,
            "color":  colors.get(name, "#4A9EFF"),
            "values": [series_data[name].get(d) for d in sorted_dates],
        }
        for name in names
    ]

    return JSONResponse({"labels": sorted_dates, "series": series, "by": by})


@router.get("/matrix")
def matrix(
    end:       Optional[str] = Query(None),
    receptors: Optional[str] = Query(None),
) -> JSONResponse:
    """Matriz receptor × transmissor para a semana mais recente no período."""
    today  = date.today()
    dt_end = _parse_date(end, today)
    sel    = _parse_receptors(receptors)

    empty = {"receptors": [], "transmitters": [], "values": [], "reference_date": None, "max_value": 0}

    try:
        con = _db_con()
        try:
            latest = _latest_date_in_table(con, dt_end.isoformat())
            if not latest:
                return JSONResponse(empty)

            if sel:
                placeholders = " OR ".join(["receptor LIKE ?" for _ in sel])
                params: list = [latest] + [f"%{r}%" for r in sel]
                rows = con.execute(
                    f"SELECT receptor, transmitter, total "
                    f"FROM active_consents "
                    f"WHERE date = ? AND ({placeholders}) "
                    f"ORDER BY receptor, transmitter",
                    params,
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT receptor, transmitter, total "
                    "FROM active_consents WHERE date = ? "
                    "ORDER BY receptor, transmitter",
                    (latest,),
                ).fetchall()

            # Totais globais por transmissor (sem filtro de receptor) — mesma semana
            global_txm_rows = con.execute(
                "SELECT transmitter, SUM(total) AS total "
                "FROM active_consents WHERE date = ? "
                "GROUP BY transmitter",
                (latest,),
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return JSONResponse(empty)

    if not rows:
        return JSONResponse(empty)

    # Pivotar em Python
    rec_order: list[str] = []
    txm_order: list[str] = []
    cell_map: dict[tuple[str, str], int] = {}

    for rec, txm, total in rows:
        if rec not in rec_order:
            rec_order.append(rec)
        if txm not in txm_order:
            txm_order.append(txm)
        cell_map[(rec, txm)] = total

    max_value = max(cell_map.values(), default=0)
    values = [
        [cell_map.get((rec, txm), 0) for txm in txm_order]
        for rec in rec_order
    ]

    # transmitter_totals: global (all receptors); grand_total_global: soma dos
    # transmissores visíveis na matriz (não necessariamente todos do ecossistema)
    txm_global: dict[str, int] = {r[0]: r[1] for r in global_txm_rows}
    grand_total_global = sum(txm_global.get(txm, 0) for txm in txm_order)

    return JSONResponse({
        "receptors":          rec_order,
        "transmitters":       txm_order,
        "values":             values,
        "reference_date":     latest,
        "max_value":          max_value,
        "transmitter_totals": txm_global,
        "grand_total_global": grand_total_global,
    })


@router.get("/ranking")
def ranking(
    end:   Optional[str] = Query(None),
    by:    str            = Query("receptor", pattern="^(receptor|transmitter)$"),
    limit: int            = Query(10, ge=1, le=50),
) -> JSONResponse:
    """Top-N receptores ou transmissores por volume de ativos + Δ% semanal."""
    today  = date.today()
    dt_end = _parse_date(end, today)
    dim_col = "receptor" if by == "receptor" else "transmitter"

    empty = {"items": [], "reference_date": None, "prev_date": None, "by": by}

    try:
        con = _db_con()
        try:
            latest = _latest_date_in_table(con, dt_end.isoformat())
            if not latest:
                return JSONResponse(empty)
            prev = _prev_date_in_table(con, latest)

            # Semana mais recente — top limit*2 para garantir cobertura do Δ%
            curr_rows = con.execute(
                f"SELECT {dim_col}, SUM(total) AS total "
                f"FROM active_consents WHERE date = ? "
                f"GROUP BY {dim_col} ORDER BY total DESC LIMIT ?",
                (latest, limit * 2),
            ).fetchall()

            prev_map: dict[str, int] = {}
            if prev:
                prev_rows = con.execute(
                    f"SELECT {dim_col}, SUM(total) AS total "
                    f"FROM active_consents WHERE date = ? "
                    f"GROUP BY {dim_col}",
                    (prev,),
                ).fetchall()
                prev_map = {r[0]: r[1] for r in prev_rows}
        finally:
            con.close()
    except Exception:
        return JSONResponse(empty)

    if not curr_rows:
        return JSONResponse(empty)

    names = [r[0] for r in curr_rows[:limit]]
    colors = _build_color_map(names)

    items = []
    for name, total in curr_rows[:limit]:
        total_prev = prev_map.get(name)
        if total_prev is not None and total_prev > 0:
            delta_pct = round((total - total_prev) / total_prev * 100, 1)
        else:
            delta_pct = None

        items.append({
            "name":        name,
            "total":       total,
            "total_prev":  total_prev,
            "delta_pct":   delta_pct,
            "color":       colors.get(name, "#4A9EFF"),
        })

    return JSONResponse({
        "items":          items,
        "reference_date": latest,
        "prev_date":      prev,
        "by":             by,
    })


@router.get("/intensity")
def intensity(
    end:       Optional[str] = Query(None),
    receptors: Optional[str] = Query(None),
) -> JSONResponse:
    """Intensidade de uso por receptor: ativos totais ÷ clientes únicos."""
    today  = date.today()
    dt_end = _parse_date(end, today)
    sel    = _parse_receptors(receptors)

    empty = {"items": [], "reference_date": None}

    try:
        con = _db_con()
        try:
            latest = _latest_date_in_table(con, dt_end.isoformat())
            if not latest:
                return JSONResponse(empty)

            filter_clause = ""
            params: list = [latest, latest]
            if sel:
                placeholders = " OR ".join(["a.receptor LIKE ?" for _ in sel])
                filter_clause = f" AND ({placeholders})"
                params += [f"%{r}%" for r in sel]

            rows = con.execute(
                f"""SELECT a.receptor,
                           SUM(a.total)                                         AS active_total,
                           u.total                                               AS unique_total,
                           CASE WHEN u.total > 0
                                THEN ROUND(1.0 * SUM(a.total) / u.total, 1)
                                ELSE NULL END                                    AS intensity
                    FROM active_consents a
                    LEFT JOIN unique_consents u
                           ON a.receptor_uuid = u.receptor_uuid AND u.date = ?
                    WHERE a.date = ?{filter_clause}
                    GROUP BY a.receptor, a.receptor_uuid, u.total
                    ORDER BY intensity DESC NULLS LAST""",
                params,
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return JSONResponse(empty)

    if not rows:
        return JSONResponse(empty)

    names = [r[0] for r in rows]
    colors = _build_color_map(names)

    items = [
        {
            "receptor":     rec,
            "active_total": active_total,
            "unique_total": unique_total,
            "intensity":    intensity_val,
            "color":        colors.get(rec, "#4A9EFF"),
        }
        for rec, active_total, unique_total, intensity_val in rows
    ]

    return JSONResponse({"items": items, "reference_date": latest})
