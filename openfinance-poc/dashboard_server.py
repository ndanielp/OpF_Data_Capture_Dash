"""
dashboard_server.py — Servidor Flask para o dashboard no browser.

Inicia em thread daemon via start_server(db_path).
Expõe endpoints JSON consumidos por gui/dashboard.html.
"""

import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

# ── Configuração ───────────────────────────────────────────────────────────────
DB_PATH: Path = Path("data/consents.db")
_PORT: int = 5432
_started = False
_lock = threading.Lock()

# ── Agrupamento de APIs (mantido igual ao tab_dashboard.py) ───────────────────
API_GROUPS = {
    "Conta":        ["accounts"],
    "Cartão":       ["credit-cards-accounts"],
    "Crédito":      ["loans", "financings", "invoice-financings",
                     "unarranged-accounts-overdraft"],
    "Investimento": ["funds", "bank-fixed-incomes", "credit-fixed-incomes",
                     "variable-incomes", "treasure-titles"],
    "Câmbio":       ["exchanges"],
    "Cadastro":     ["customers"],
}
RESOURCES_API = "resources"
EXCLUDED_APIS = {"consents"}
_ORDERED_APIS: list[str] = [api for apis in API_GROUPS.values() for api in apis]

_API_LABELS: dict[str, str] = {
    "accounts":                      "accounts",
    "credit-cards-accounts":         "credit\ncards",
    "loans":                         "loans",
    "financings":                    "financings",
    "invoice-financings":            "invoice\nfin.",
    "unarranged-accounts-overdraft": "overdraft",
    "funds":                         "funds",
    "bank-fixed-incomes":            "bank\nfixed",
    "credit-fixed-incomes":          "credit\nfixed",
    "variable-incomes":              "variable",
    "treasure-titles":               "treasure",
    "exchanges":                     "exchanges",
    "customers":                     "customers",
}

# ── Cores de marca ─────────────────────────────────────────────────────────────
_BRAND = [
    ("bradesco",        "#CC092F"),
    ("nubank",          "#8B1CF0"),
    ("itaú",            "#EC7000"),
    ("itau",            "#EC7000"),
    ("santander",       "#EC0000"),
    ("caixa",           "#005CA9"),
    ("mercado pago",    "#00A9E0"),
    ("picpay",          "#21C25E"),
    ("banco do brasil", "#F9A800"),
    ("belvo",           "#4A9EFF"),
    ("recargapay",      "#7B68EE"),
    ("shopee",          "#FF5722"),
    ("pagseguro",       "#34B7F1"),
    ("cloudwalk",       "#9C27B0"),
]

_FALLBACK_COLORS = [
    "#4A9EFF", "#7B68EE", "#FF5722", "#34B7F1",
    "#9C27B0", "#F9E68C", "#cba6f7", "#f38ba8",
    "#fab387", "#94e2d5", "#b4befe", "#a6e3a1",
]


def _brand_color(receptor: str) -> str | None:
    name = receptor.lower()
    for key, color in _BRAND:
        if key in name:
            return color
    return None


def _build_color_map(receptors: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    fb_idx = 0
    for r in receptors:
        c = _brand_color(r)
        if c:
            result[r] = c
            used.add(c)
        else:
            while fb_idx < len(_FALLBACK_COLORS) and _FALLBACK_COLORS[fb_idx] in used:
                fb_idx += 1
            c = _FALLBACK_COLORS[fb_idx % len(_FALLBACK_COLORS)]
            used.add(c)
            fb_idx += 1
            result[r] = c
    return result


# ── Leitura do banco ───────────────────────────────────────────────────────────

def _load_consents() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql(
            "SELECT date, receptor, total FROM unique_consents",
            con, parse_dates=["date"],
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def _load_api() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql(
            "SELECT date, receptor, api, status, total FROM api_requests",
            con, parse_dates=["date"],
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


# ── Helpers de filtragem ───────────────────────────────────────────────────────

def _parse_date(s: str | None, fallback: date) -> date:
    if not s:
        return fallback
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback


def _filter_by_date(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df[mask]


def _parse_receptors(receptors_param: str | None) -> list[str] | None:
    if not receptors_param:
        return None
    parts = [r.strip() for r in receptors_param.split(",") if r.strip()]
    return parts if parts else None


def _top10_with_bradesco(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
    top10 = totals.nlargest(10).index.tolist()
    for r in totals.index:
        if "bradesco" in r.lower() and r not in top10:
            top10 = top10[:9] + [r]
            break
    return top10


def _fmt_number(x: float) -> str:
    if x >= 1_000_000_000:
        return f"{x / 1_000_000_000:.1f}B"
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}k"
    return str(int(x))


# ── Flask app ──────────────────────────────────────────────────────────────────

_GUI_DIR = Path(__file__).parent / "gui"

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(str(_GUI_DIR), "dashboard.html")


@app.route("/api/receptors")
def receptors():
    df = _load_consents()
    if df.empty:
        return jsonify([])
    all_recs = (
        df.groupby("receptor")["total"].sum()
        .sort_values(ascending=False).index.tolist()
    )
    colors = _build_color_map(all_recs)
    top10 = set(_top10_with_bradesco(df))
    return jsonify([
        {"label": r, "color": colors.get(r, "#4A5270"), "top": r in top10}
        for r in all_recs
    ])


@app.route("/api/consents")
def consents_endpoint():
    today = date.today()
    start = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end   = _parse_date(request.args.get("end"),   today)
    sel   = _parse_receptors(request.args.get("receptors"))

    df = _load_consents()
    df = _filter_by_date(df, start, end)
    if df.empty:
        return jsonify({"labels": [], "datasets": []})

    if sel:
        receptors = sel
    else:
        receptors = _top10_with_bradesco(df)

    df = df[df["receptor"].isin(receptors)]
    if df.empty:
        return jsonify({"labels": [], "datasets": []})

    df["month"] = df["date"].dt.to_period("M")
    monthly = (
        df.groupby(["month", "receptor"])["total"]
        .sum().reset_index()
    )
    all_months = sorted(monthly["month"].unique())
    labels = [str(m) for m in all_months]

    colors = _build_color_map(receptors)
    datasets = []
    for r in receptors:
        sub = monthly[monthly["receptor"] == r].set_index("month")
        data = [int(sub["total"].get(m, 0)) for m in all_months]
        color = colors.get(r, "#4A9EFF")
        datasets.append({
            "label": r,
            "data": data,
            "borderColor": color,
            "backgroundColor": color + "18",
            "borderWidth": 2,
            "pointRadius": 3,
            "pointHoverRadius": 5,
            "pointBackgroundColor": color,
            "pointBorderColor": "transparent",
            "tension": 0.35,
            "fill": False,
        })
    return jsonify({"labels": labels, "datasets": datasets})


@app.route("/api/api-requests")
def api_requests_endpoint():
    today = date.today()
    start     = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end       = _parse_date(request.args.get("end"),   today)
    sel       = _parse_receptors(request.args.get("receptors"))
    status    = request.args.get("status", "all")
    normalize = request.args.get("normalize", "0") == "1"

    df_api = _load_api()
    df_api = _filter_by_date(df_api, start, end)
    if df_api.empty:
        return jsonify({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    df = df_api[~df_api["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
    if status == "200":
        df = df[df["status"] == 200]
    elif status == "500":
        df = df[df["status"] == 500]

    if df.empty:
        return jsonify({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    if sel:
        top_receptors = [r for r in sel if r in df["receptor"].values]
    else:
        df_cons = _load_consents()
        df_cons = _filter_by_date(df_cons, start, end)
        base = df_cons if not df_cons.empty else df
        top_receptors = _top10_with_bradesco(base)
        top_receptors = [r for r in top_receptors if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_receptors)]
    if df.empty:
        return jsonify({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    available_apis = set(df["api"].unique())
    ordered_cols   = [a for a in _ORDERED_APIS if a in available_apis]

    pivot = (
        df.groupby(["receptor", "api"])["total"]
        .sum().unstack(fill_value=0)
        .reindex(index=top_receptors, columns=ordered_cols)
        .fillna(0)
    )
    data = pivot.values.astype(float)

    if normalize:
        df_cons = _load_consents()
        df_cons = _filter_by_date(df_cons, start, end)
        ct = df_cons.groupby("receptor")["total"].sum() if not df_cons.empty else pd.Series(dtype=float)
        for i, rec in enumerate(pivot.index):
            n = float(ct.get(rec, 0))
            if n > 0:
                data[i] /= n

    # Groups info for header rendering
    groups_info = []
    col_idx = 0
    for grupo, apis in API_GROUPS.items():
        cols = [a for a in apis if a in available_apis]
        if not cols:
            continue
        groups_info.append({"label": grupo, "start": col_idx, "span": len(cols)})
        col_idx += len(cols)

    max_val = float(data.max()) if data.size > 0 else 0
    return jsonify({
        "groups":    groups_info,
        "apis":      [{"id": a, "label": _API_LABELS.get(a, a)} for a in ordered_cols],
        "receptors": list(pivot.index),
        "values":    data.tolist(),
        "max_val":   max_val,
        "normalize": normalize,
    })


@app.route("/api/resources")
def resources_endpoint():
    today = date.today()
    start     = _parse_date(request.args.get("start"), today - timedelta(days=365))
    end       = _parse_date(request.args.get("end"),   today)
    sel       = _parse_receptors(request.args.get("receptors"))
    status    = request.args.get("status", "all")
    normalize = request.args.get("normalize", "0") == "1"

    df_api = _load_api()
    df_api = _filter_by_date(df_api, start, end)
    if df_api.empty:
        return jsonify({"receptors": [], "values": [], "colors": []})

    df = df_api[df_api["api"] == RESOURCES_API].copy()
    if status == "200":
        df = df[df["status"] == 200]
    elif status == "500":
        df = df[df["status"] == 500]

    if df.empty:
        return jsonify({"receptors": [], "values": [], "colors": []})

    if sel:
        top_receptors = [r for r in sel if r in df["receptor"].values]
    else:
        df_cons = _load_consents()
        df_cons = _filter_by_date(df_cons, start, end)
        base = df_cons if not df_cons.empty else df
        top_receptors = _top10_with_bradesco(base)
        top_receptors = [r for r in top_receptors if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_receptors)]
    if df.empty:
        return jsonify({"receptors": [], "values": [], "colors": []})

    totals = df.groupby("receptor")["total"].sum().reindex(top_receptors).fillna(0)
    values = totals.values.astype(float)

    if normalize:
        df_cons = _load_consents()
        df_cons = _filter_by_date(df_cons, start, end)
        ct = df_cons.groupby("receptor")["total"].sum() if not df_cons.empty else pd.Series(dtype=float)
        for i, rec in enumerate(totals.index):
            n = float(ct.get(rec, 0))
            if n > 0:
                values[i] /= n

    colors_map = _build_color_map(list(totals.index))
    colors = [colors_map.get(r, "#4A9EFF") for r in totals.index]

    return jsonify({
        "receptors": list(totals.index),
        "values":    values.tolist(),
        "colors":    colors,
        "normalize": normalize,
    })


@app.route("/api/stats")
def stats_endpoint():
    try:
        con = sqlite3.connect(str(DB_PATH))
        n_c = con.execute("SELECT count(*) FROM unique_consents").fetchone()[0]
        n_a = con.execute("SELECT count(*) FROM api_requests").fetchone()[0]
        last = con.execute(
            "SELECT MAX(date) FROM unique_consents"
        ).fetchone()[0] or ""
        con.close()
        return jsonify({
            "db":           DB_PATH.name,
            "consents":     n_c,
            "api_requests": n_a,
            "last_updated": last[:10] if last else "",
        })
    except Exception:
        return jsonify({
            "db":           DB_PATH.name,
            "consents":     0,
            "api_requests": 0,
            "last_updated": "",
        })


# ── Inicialização ──────────────────────────────────────────────────────────────

def set_db(path: Path) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def start_server(db_path: Path | str, port: int = 5432) -> None:
    """Inicia o servidor Flask em thread daemon. Idempotente."""
    global _started, _PORT
    with _lock:
        if _started:
            set_db(Path(db_path))
            return
        set_db(Path(db_path))
        _PORT = port
        _started = True

    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    t = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
        name="dashboard-flask",
    )
    t.start()
