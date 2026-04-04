"""
dashboard_server.py — FastAPI backend para o Dashboard
======================================================
Servidor web local que expõe dados extraídos de sqlite
e os entrega formatados (JSON) para a interface HTML/JS.
"""

import sqlite3
import uvicorn
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config

# ── Agrupamentos e Cores ───────────────────────────────────────────────────────
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
_ORDERED_APIS = [api for apis in API_GROUPS.values() for api in apis]

_API_LABELS = {
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
    result = {}
    used = set()
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

# ── Data Loading & Logic ───────────────────────────────────────────────────────

def _load_consents() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(config.DB_PATH))
        df = pd.read_sql("SELECT date, receptor, total, cpf, cnpj FROM unique_consents", con, parse_dates=["date"])
        con.close()
        return df
    except Exception:
        return pd.DataFrame()

def _load_api() -> pd.DataFrame:
    try:
        con = sqlite3.connect(str(config.DB_PATH))
        df = pd.read_sql("SELECT date, receptor, api, status, total FROM api_requests", con, parse_dates=["date"])
        con.close()
        return df
    except Exception:
        return pd.DataFrame()

def _parse_date(s: str | None, fallback: date) -> date:
    if not s: return fallback
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback

def _filter_by_date(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or "date" not in df.columns: return df
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    return df[mask]

def _parse_receptors(receptors_param: str | None) -> list[str] | None:
    if not receptors_param: return None
    parts = [r.strip() for r in receptors_param.split(",") if r.strip()]
    return parts if parts else None

def _top10_with_bradesco(df: pd.DataFrame) -> list[str]:
    if df.empty: return []
    totals = df.groupby("receptor")["total"].sum().sort_values(ascending=False)
    top10 = totals.nlargest(10).index.tolist()
    for r in totals.index:
        if "bradesco" in r.lower() and r not in top10:
            top10 = top10[:9] + [r]
            break
    return top10

# ── FastAPI App ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="OPF Batch Dashboard", lifespan=lifespan)

GUI_DIR = Path(__file__).parent / "gui"

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = GUI_DIR / "dashboard.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.get("/api/receptors", response_class=JSONResponse)
def get_receptors():
    df = _load_consents()
    if df.empty: return JSONResponse([])
    all_recs = df.groupby("receptor")["total"].sum().sort_values(ascending=False).index.tolist()
    colors = _build_color_map(all_recs)
    top10 = set(_top10_with_bradesco(df))
    return JSONResponse([
        {"label": r, "color": colors.get(r, "#4A5270"), "top": r in top10}
        for r in all_recs
    ])

@app.get("/api/consents", response_class=JSONResponse)
def get_consents(start: str = None, end: str = None, receptors: str = None):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)

    df = _load_consents()
    df = _filter_by_date(df, dt_start, dt_end)
    if df.empty: return JSONResponse({"labels": [], "datasets": [], "ranking_pf": [], "ranking_pj": []})

    recs = sel if sel else _top10_with_bradesco(df)
    df = df[df["receptor"].isin(recs)]
    if df.empty: return JSONResponse({"labels": [], "datasets": [], "ranking_pf": [], "ranking_pj": []})

    for col in ["cpf", "cnpj", "total"]:
        if col not in df.columns:
            df[col] = 0

    df["week"] = df["date"].dt.strftime("%Y-%m-%d")
    weekly = df.groupby(["week", "receptor"])[["total", "cpf", "cnpj"]].max().reset_index()
    all_weeks = sorted(weekly["week"].unique())
    labels = [str(w) for w in all_weeks]

    colors = _build_color_map(recs)
    datasets = []
    
    last_week = all_weeks[-1] if all_weeks else None
    wt_idx = max(0, len(all_weeks) - 9)
    base_week = all_weeks[wt_idx] if all_weeks else None

    latest_data = weekly[weekly["week"] == last_week] if last_week else pd.DataFrame()
    base_data = weekly[weekly["week"] == base_week] if base_week else pd.DataFrame()

    base_pf = dict(zip(base_data["receptor"], base_data["cpf"])) if not base_data.empty else {}
    base_pj = dict(zip(base_data["receptor"], base_data["cnpj"])) if not base_data.empty else {}

    ranking_pf = []
    for _, row in latest_data.sort_values(by="cpf", ascending=False).iterrows():
        rec, val = row["receptor"], row["cpf"]
        base = base_pf.get(rec, 0)
        gw = round(((val - base) / base) * 100, 1) if base > 0 else (round(float(val * 100), 1) if val > 0 else 0.0)
        ranking_pf.append({"receptor": rec, "cpf": val, "growth": gw})

    ranking_pj = []
    for _, row in latest_data.sort_values(by="cnpj", ascending=False).iterrows():
        rec, val = row["receptor"], row["cnpj"]
        base = base_pj.get(rec, 0)
        gw = round(((val - base) / base) * 100, 1) if base > 0 else (round(float(val * 100), 1) if val > 0 else 0.0)
        ranking_pj.append({"receptor": rec, "cnpj": val, "growth": gw})

    def calc_growth(arr):
        if not arr: return 0.0
        fst, lst = arr[0], arr[-1]
        if fst == 0: return round(float(lst * 100), 1) if lst > 0 else 0.0
        return round(((lst - fst) / fst) * 100, 1)

    for r in recs:
        sub = weekly[weekly["receptor"] == r].set_index("week")
        arr_total = [int(sub["total"].get(w, 0)) for w in all_weeks]
        arr_pf    = [int(sub["cpf"].get(w, 0)) for w in all_weeks]
        arr_pj    = [int(sub["cnpj"].get(w, 0)) for w in all_weeks]
        color = colors.get(r, "#4A9EFF")
        
        datasets.append({
            "label": r,
            "data": arr_total, 
            "data_all": arr_total,
            "data_pf": arr_pf,
            "data_pj": arr_pj,
            "growth_all": calc_growth(arr_total),
            "growth_pf": calc_growth(arr_pf),
            "growth_pj": calc_growth(arr_pj),
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
        
    return JSONResponse({
        "labels": labels, 
        "datasets": datasets,
        "ranking_pf": ranking_pf,
        "ranking_pj": ranking_pj
    })

@app.get("/api/api-requests", response_class=JSONResponse)
def get_api_requests(start: str = None, end: str = None, receptors: str = None, status: str = "all", normalize: str = "0"):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)
    norm     = normalize == "1"

    df_api = _load_api()
    df_api = _filter_by_date(df_api, dt_start, dt_end)
    if df_api.empty:
        return JSONResponse({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    df = df_api[~df_api["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    if df.empty:
        return JSONResponse({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    if sel:
        top_reps = [r for r in sel if r in df["receptor"].values]
    else:
        df_cons = _filter_by_date(_load_consents(), dt_start, dt_end)
        base = df_cons if not df_cons.empty else df
        top_reps = [r for r in _top10_with_bradesco(base) if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_reps)]
    if df.empty:
        return JSONResponse({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    available_apis = set(df["api"].unique())
    ordered_cols   = [a for a in _ORDERED_APIS if a in available_apis]

    pivot = (
        df.groupby(["receptor", "api"])["total"]
        .sum().unstack(fill_value=0)
        .reindex(index=top_reps, columns=ordered_cols)
        .fillna(0)
    )
    data = pivot.values.astype(float)

    if norm:
        df_cons = _filter_by_date(_load_consents(), dt_start, dt_end)
        ct = df_cons.groupby("receptor")["total"].sum() if not df_cons.empty else pd.Series(dtype=float)
        for i, rec in enumerate(pivot.index):
            n = float(ct.get(rec, 0))
            if n > 0: data[i] /= n

    groups_info = []
    col_idx = 0
    for grupo, apis in API_GROUPS.items():
        cols = [a for a in apis if a in available_apis]
        if not cols: continue
        groups_info.append({"label": grupo, "start": col_idx, "span": len(cols)})
        col_idx += len(cols)

    max_val = float(data.max()) if data.size > 0 else 0
    return JSONResponse({
        "groups":    groups_info,
        "apis":      [{"id": a, "label": _API_LABELS.get(a, a)} for a in ordered_cols],
        "receptors": list(pivot.index),
        "values":    data.tolist(),
        "max_val":   max_val,
        "normalize": norm,
    })

@app.get("/api/resources", response_class=JSONResponse)
def get_resources(start: str = None, end: str = None, receptors: str = None, status: str = "all", normalize: str = "0"):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)
    norm     = normalize == "1"

    df_api = _load_api()
    df_api = _filter_by_date(df_api, dt_start, dt_end)
    if df_api.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    df = df_api[df_api["api"] == RESOURCES_API].copy()
    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    if sel:
        top_reps = [r for r in sel if r in df["receptor"].values]
    else:
        df_cons = _filter_by_date(_load_consents(), dt_start, dt_end)
        base = df_cons if not df_cons.empty else df
        top_reps = [r for r in _top10_with_bradesco(base) if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_reps)]
    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    totals = df.groupby("receptor")["total"].sum().reindex(top_reps).fillna(0)
    values = totals.values.astype(float)

    if norm:
        df_cons = _filter_by_date(_load_consents(), dt_start, dt_end)
        ct = df_cons.groupby("receptor")["total"].sum() if not df_cons.empty else pd.Series(dtype=float)
        for i, rec in enumerate(totals.index):
            n = float(ct.get(rec, 0))
            if n > 0: values[i] /= n

    colors_map = _build_color_map(list(totals.index))
    colors = [colors_map.get(r, "#4A9EFF") for r in totals.index]

    return JSONResponse({
        "receptors": list(totals.index),
        "values":    values.tolist(),
        "colors":    colors,
        "normalize": norm,
    })

@app.get("/api/stats", response_class=JSONResponse)
def get_stats():
    try:
        con = sqlite3.connect(str(config.DB_PATH))
        n_c = con.execute("SELECT count(*) FROM unique_consents").fetchone()[0]
        n_a = con.execute("SELECT count(*) FROM api_requests").fetchone()[0]
        min_date = con.execute("SELECT MIN(date) FROM unique_consents").fetchone()[0] or ""
        max_date = con.execute("SELECT MAX(date) FROM unique_consents").fetchone()[0] or ""
        con.close()
        return JSONResponse({
            "db":           config.DB_PATH.name,
            "consents":     n_c,
            "api_requests": n_a,
            "min_date":     min_date[:10] if min_date else "",
            "max_date":     max_date[:10] if max_date else "",
            "last_updated": max_date[:10] if max_date else "",
        })
    except Exception:
        return JSONResponse({
            "db":           config.DB_PATH.name,
            "consents":     0,
            "api_requests": 0,
            "min_date":     "",
            "max_date":     "",
            "last_updated": "",
        })

app.mount("/static", StaticFiles(directory=str(GUI_DIR)), name="static")

def run_server(port: int = 8000):
    GUI_DIR.mkdir(parents=True, exist_ok=True)
    print(f"🚀 Iniciando Dashboard Servidor em http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
