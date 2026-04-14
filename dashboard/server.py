"""
dashboard_server.py — FastAPI backend para o Dashboard
======================================================
Servidor web local que expõe dados extraídos de sqlite
e os entrega formatados (JSON) para a interface HTML/JS.
"""

import sqlite3
import threading
import time as _time
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
    "Cadastro":     ["customers-pf", "customers-pj"],
}
RESOURCES_API = "resources"
EXCLUDED_APIS = {"consents"}
_ORDERED_APIS = [api for apis in API_GROUPS.values() for api in apis]

_API_LABELS = {
    "accounts":                      "Conta",
    "credit-cards-accounts":         "Cartão",
    "loans":                         "Empréstimo",
    "financings":                    "Financiamento",
    "invoice-financings":            "Dir.\nCreditório",
    "unarranged-accounts-overdraft": "Adiantamento",
    "funds":                         "Fundos",
    "bank-fixed-incomes":            "Renda Fixa\nBancária",
    "credit-fixed-incomes":          "Renda Fixa\nCrédito",
    "variable-incomes":              "Renda\nVariável",
    "treasure-titles":               "Tesouro",
    "exchanges":                     "Câmbio",
    "customers-pf":                  "Cadastro\nPF",
    "customers-pj":                  "Cadastro\nPJ",
}

# APIs que usam denominador PF (cpf) ou PJ (cnpj) na normalização
_NORM_CPF_APIS  = {"customers-pf"}
_NORM_CNPJ_APIS = {"customers-pj"}

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

def _is_pj_customer_endpoint(label: str) -> bool:
    """Detecta se o label de endpoint de customers é Pessoa Jurídica."""
    l = label.lower()
    return "juríd" in l or "juridic" in l or "jurídic" in l

def _normalize_customer_ep_label(label: str) -> str:
    """Mapeia labels raw dos endpoints de customers para nomes curtos padronizados."""
    l = label.lower()
    suffix = " PJ" if _is_pj_customer_endpoint(label) else " PF"
    if "identif"  in l: return "Identificação"  + suffix
    if "qualif"   in l: return "Qualificação"   + suffix
    if "relacion" in l: return "Relacionamento" + suffix
    return label  # fallback: mantém original

def _load_api_with_endpoints() -> pd.DataFrame:
    """Carrega api_requests com detalhe de endpoint.
    A API 'customers' é dividida em 'customers-pf' / 'customers-pj' pelo
    label do endpoint, e os labels são normalizados para nomes curtos.
    """
    try:
        con = sqlite3.connect(str(config.DB_PATH))
        df = pd.read_sql(
            """
            SELECT date, receptor, api, endpoint_id, endpoint, status, SUM(total) AS total
            FROM api_requests
            WHERE endpoint_id <> 0
            GROUP BY date, receptor, api, endpoint_id, endpoint, status
            """,
            con, parse_dates=["date"]
        )
        con.close()
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Split customers → customers-pf / customers-pj + normaliza labels dos endpoints
    mask = df["api"] == "customers"
    if mask.any():
        df.loc[mask, "api"] = df.loc[mask, "endpoint"].apply(
            lambda lbl: "customers-pj" if _is_pj_customer_endpoint(lbl) else "customers-pf"
        )
        df.loc[mask, "endpoint"] = df.loc[mask, "endpoint"].apply(_normalize_customer_ep_label)

    return df

def _load_api() -> pd.DataFrame:
    """Agrega api_requests por (date, receptor, api, status); customers já dividido em PF/PJ."""
    df = _load_api_with_endpoints()
    if df.empty:
        return df
    return (
        df.groupby(["date", "receptor", "api", "status"], as_index=False)["total"]
        .sum()
    )

# ── Cache em memória ──────────────────────────────────────────────────────────
# Os DataFrames são grandes; relê-los a cada request é o principal gargalo.
# O cache é preenchido no startup e invalidado a cada _CACHE_TTL segundos
# (ou forçadamente via POST /api/refresh-cache após uma nova coleta).

_CACHE: dict = {"consents": None, "api": None, "ts": 0.0}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL  = 300  # segundos

def _refresh_cache(force: bool = False) -> None:
    """Relê o SQLite e atualiza _CACHE. Thread-safe."""
    with _CACHE_LOCK:
        if not force and _time.time() - _CACHE["ts"] < _CACHE_TTL:
            return
        _CACHE["consents"] = _load_consents()
        _CACHE["api"]      = _load_api_with_endpoints()
        _CACHE["ts"]       = _time.time()

def _cached_consents() -> pd.DataFrame:
    _refresh_cache()
    df = _CACHE["consents"]
    return df if df is not None else pd.DataFrame()

def _cached_api_ep() -> pd.DataFrame:
    _refresh_cache()
    df = _CACHE["api"]
    return df if df is not None else pd.DataFrame()

def _cached_api() -> pd.DataFrame:
    """Versão agregada de _cached_api_ep() — equivalente a _load_api()."""
    df = _cached_api_ep()
    if df.empty:
        return df
    return df.groupby(["date", "receptor", "api", "status"], as_index=False)["total"].sum()


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
    _refresh_cache(force=True)
    yield

app = FastAPI(title="OPF Batch Dashboard", lifespan=lifespan)

GUI_DIR = Path(__file__).parent / "gui"

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = GUI_DIR / "dashboard.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.get("/api/receptors", response_class=JSONResponse)
def get_receptors():
    df = _cached_consents()
    if df.empty: return JSONResponse([])
    all_recs = df.groupby("receptor")["total"].sum().sort_values(ascending=False).index.tolist()
    colors = _build_color_map(all_recs)
    top10 = set(_top10_with_bradesco(df))
    return JSONResponse([
        {"label": r, "color": colors.get(r, "#4A5270"), "top": r in top10}
        for r in all_recs
    ])

@app.post("/api/refresh-cache")
def post_refresh_cache():
    """Invalida e recarrega o cache em memória. Chamar após uma nova coleta de dados."""
    _refresh_cache(force=True)
    return {"ok": True, "cached_at": _CACHE["ts"]}


@app.get("/api/consents", response_class=JSONResponse)
def get_consents(start: str = None, end: str = None, receptors: str = None):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)

    df = _cached_consents()
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

    # Calcula diferença de dias para variação diária
    try:
        d_last = datetime.strptime(last_week, "%Y-%m-%d")
        d_base = datetime.strptime(base_week, "%Y-%m-%d")
        days_diff = (d_last - d_base).days
    except:
        days_diff = 1
    days_diff = max(1, days_diff)

    ranking_pf = []
    for _, row in latest_data.sort_values(by="cpf", ascending=False).iterrows():
        rec, val = row["receptor"], row["cpf"]
        base = base_pf.get(rec, 0)
        gw = round(((val - base) / base) * 100, 1) if base > 0 else (round(float(val * 100), 1) if val > 0 else 0.0)
        daily = round((val - base) / days_diff, 1)
        ranking_pf.append({"receptor": rec, "cpf": val, "growth": gw, "daily_delta": daily})

    ranking_pj = []
    for _, row in latest_data.sort_values(by="cnpj", ascending=False).iterrows():
        rec, val = row["receptor"], row["cnpj"]
        base = base_pj.get(rec, 0)
        gw = round(((val - base) / base) * 100, 1) if base > 0 else (round(float(val * 100), 1) if val > 0 else 0.0)
        daily = round((val - base) / days_diff, 1)
        ranking_pj.append({"receptor": rec, "cnpj": val, "growth": gw, "daily_delta": daily})

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

    # Lê do cache uma única vez — reutilizado para df_api e df_ep abaixo
    _df_ep_full = _cached_api_ep()
    df_api = (
        _df_ep_full.groupby(["date", "receptor", "api", "status"], as_index=False)["total"].sum()
        if not _df_ep_full.empty else pd.DataFrame()
    )
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
        df_cons = _filter_by_date(_cached_consents(), dt_start, dt_end)
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
    data     = pivot.values.astype(float)
    data_raw = data.copy()              # chamadas brutas — usadas para a coluna Total
    ct_total = pd.Series(dtype=float)  # populado dentro do bloco norm; visível depois

    if norm:
        df_cons = _filter_by_date(_cached_consents(), dt_start, dt_end)
        if not df_cons.empty:
            ct_total = df_cons.groupby("receptor")["total"].sum()
            ct_cpf   = df_cons.groupby("receptor")["cpf"].sum()
            ct_cnpj  = df_cons.groupby("receptor")["cnpj"].sum()
        else:
            ct_cpf = ct_cnpj = pd.Series(dtype=float)
        # Converte de semanal para mensal; Cadastro PF/PJ usam denominadores específicos
        for i, rec in enumerate(pivot.index):
            for j, col in enumerate(ordered_cols):
                if col in _NORM_CPF_APIS:
                    n = float(ct_cpf.get(rec, 0))
                elif col in _NORM_CNPJ_APIS:
                    n = float(ct_cnpj.get(rec, 0))
                else:
                    n = float(ct_total.get(rec, 0))
                if n > 0:
                    data[i, j] = (data[i, j] / n) / 7 * 30

    # ── Intensidade global por receptor ───────────────────────────────────────
    # Usa denominador único (total consents) para evitar distorção de somar
    # frações com denominadores diferentes (total vs cpf vs cnpj por API).
    raw_row_sums = data_raw.sum(axis=1)
    if norm:
        denom = ct_total.reindex(list(pivot.index)).fillna(0).replace(0, float("nan"))
        row_totals = (
            pd.Series(raw_row_sums, index=list(pivot.index)) / denom / 7 * 30
        ).fillna(0).values
    else:
        row_totals = raw_row_sums

    # ── Ordenar receptores por intensidade global decrescente ─────────────────
    sort_idx      = row_totals.argsort()[::-1]
    data          = data[sort_idx]
    top_reps      = [top_reps[i] for i in sort_idx]
    row_totals    = row_totals[sort_idx]
    max_row_total = float(row_totals.max()) if row_totals.size > 0 else 0.0

    groups_info = []
    col_idx = 0
    for grupo, apis in API_GROUPS.items():
        cols = [a for a in apis if a in available_apis]
        if not cols: continue
        groups_info.append({"label": grupo, "start": col_idx, "span": len(cols)})
        col_idx += len(cols)

    max_val = float(data.max()) if data.size > 0 else 0

    # ── Endpoint breakdown por API ─────────────────────────────────────────────
    endpoints_by_api: dict = {}
    endpoint_max_val = 0.0
    df_ep = _df_ep_full  # reutiliza o cache já lido acima
    df_ep = _filter_by_date(df_ep, dt_start, dt_end)
    if not df_ep.empty:
        if status == "200": df_ep = df_ep[df_ep["status"] == 200]
        elif status == "500": df_ep = df_ep[df_ep["status"] == 500]
        df_ep = df_ep[df_ep["receptor"].isin(top_reps)]
        df_ep = df_ep[~df_ep["api"].isin(EXCLUDED_APIS | {RESOURCES_API})]

        if not df_ep.empty:
            # Pivot por (receptor, api, endpoint_id)
            ep_pivot = (
                df_ep.groupby(["receptor", "api", "endpoint_id", "endpoint"])["total"]
                .sum().reset_index()
            )
            if norm and not df_ep.empty:
                df_cons_ep = _filter_by_date(_cached_consents(), dt_start, dt_end)
                if not df_cons_ep.empty:
                    ct_ep_total = df_cons_ep.groupby("receptor")["total"].sum()
                    ct_ep_cpf   = df_cons_ep.groupby("receptor")["cpf"].sum()
                    ct_ep_cnpj  = df_cons_ep.groupby("receptor")["cnpj"].sum()
                else:
                    ct_ep_total = ct_ep_cpf = ct_ep_cnpj = pd.Series(dtype=float)
                def _norm_ep(row):
                    if row["api"] in _NORM_CPF_APIS:
                        n = float(ct_ep_cpf.get(row["receptor"], 0))
                    elif row["api"] in _NORM_CNPJ_APIS:
                        n = float(ct_ep_cnpj.get(row["receptor"], 0))
                    else:
                        n = float(ct_ep_total.get(row["receptor"], 0))
                    return (row["total"] / n) / 7 * 30 if n > 0 else 0.0
                ep_pivot["total"] = ep_pivot.apply(_norm_ep, axis=1)

            for api_id in ordered_cols:
                api_ep = ep_pivot[ep_pivot["api"] == api_id]
                if api_ep.empty:
                    continue
                # Headers: endpoint_ids únicos ordenados por id
                ep_headers = (
                    api_ep[["endpoint_id", "endpoint"]]
                    .drop_duplicates()
                    .sort_values("endpoint_id")
                )
                headers = [{"id": int(r["endpoint_id"]), "label": r["endpoint"]} for _, r in ep_headers.iterrows()]
                ep_ids = [h["id"] for h in headers]
                # Valores: [receptor][endpoint]
                values_ep = []
                for rec in top_reps:
                    row_vals = []
                    rec_ep = api_ep[api_ep["receptor"] == rec]
                    for ep_id in ep_ids:
                        match = rec_ep[rec_ep["endpoint_id"] == ep_id]["total"]
                        row_vals.append(float(match.iloc[0]) if not match.empty else 0.0)
                    values_ep.append(row_vals)
                endpoints_by_api[api_id] = {"headers": headers, "values": values_ep}
                local_max = max((v for row in values_ep for v in row), default=0.0)
                if local_max > endpoint_max_val:
                    endpoint_max_val = local_max

    return JSONResponse({
        "groups":          groups_info,
        "apis":            [{"id": a, "label": _API_LABELS.get(a, a)} for a in ordered_cols],
        "receptors":       top_reps,
        "values":          data.tolist(),
        "max_val":         max_val,
        "normalize":       norm,
        "endpoints_by_api": endpoints_by_api,
        "endpoint_max_val": endpoint_max_val,
        "row_totals":      row_totals.tolist(),
        "max_row_total":   max_row_total,
    })

@app.get("/api/api-requests-timeseries", response_class=JSONResponse)
def get_api_requests_timeseries(
    start: str = None, end: str = None,
    receptors: str = None,
    apis: str = None,
    endpoints: str = None,
    status: str = "all",
    normalize: str = "0",
):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    norm     = normalize == "1"
    sel      = _parse_receptors(receptors)

    if not sel:
        return JSONResponse({"dates": [], "series": [], "normalize": norm, "filter_label": ""})

    df = _cached_api_ep()
    df = _filter_by_date(df, dt_start, dt_end)
    if df.empty:
        return JSONResponse({"dates": [], "series": [], "normalize": norm, "filter_label": ""})

    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    df = df[df["receptor"].isin(sel)]
    df = df[~df["api"].isin(EXCLUDED_APIS)]

    filter_parts = []
    if endpoints:
        ep_ids = [int(e) for e in endpoints.split(",") if e.strip().isdigit()]
        if ep_ids:
            df = df[df["endpoint_id"].isin(ep_ids)]
            # Labels já normalizados pelo _load_api_with_endpoints
            ep_label_map = (
                df[["endpoint_id", "endpoint"]].drop_duplicates()
                .set_index("endpoint_id")["endpoint"].to_dict()
            )
            filter_parts = [ep_label_map.get(e, str(e)) for e in ep_ids]
    elif apis:
        api_list = [a.strip() for a in apis.split(",") if a.strip()]
        if api_list:
            df = df[df["api"].isin(api_list)]
            filter_parts = [_API_LABELS.get(a, a).replace("\n", " ") for a in api_list]

    if df.empty:
        return JSONResponse({"dates": [], "series": [], "normalize": norm, "filter_label": " | ".join(filter_parts)})

    # Agrega por (date, receptor)
    agg = df.groupby(["date", "receptor"])["total"].sum().reset_index()
    agg["date_str"] = agg["date"].dt.strftime("%Y-%m-%d")

    all_dates = sorted(agg["date_str"].unique())

    if norm:
        # Normalização semana a semana: chamadas / consentimentos naquela semana
        # Denominador: consentimentos do receptor na mesma data (semana)
        apis_in_filter = set(df["api"].unique())
        use_cpf  = apis_in_filter <= _NORM_CPF_APIS
        use_cnpj = apis_in_filter <= _NORM_CNPJ_APIS
        cons_col = "cpf" if use_cpf else ("cnpj" if use_cnpj else "total")
        df_cons = _filter_by_date(_cached_consents(), dt_start, dt_end)
        if not df_cons.empty:
            cons_weekly = (
                df_cons.groupby(["date", "receptor"])[cons_col]
                .sum().reset_index()
                .rename(columns={cons_col: "_cons"})
            )
            agg = agg.merge(cons_weekly, on=["date", "receptor"], how="left")
            agg["total"] = (agg["total"] / agg["_cons"].replace(0, float("nan"))).fillna(0.0)
            agg = agg.drop(columns=["_cons"])

    colors_map = _build_color_map(sel)
    series = []
    for rec in sel:
        rec_data = agg[agg["receptor"] == rec].set_index("date_str")["total"]
        values = [float(rec_data[d]) if d in rec_data.index else None for d in all_dates]
        series.append({
            "receptor": rec,
            "color":    colors_map.get(rec, "#4A9EFF"),
            "values":   values,
        })

    return JSONResponse({
        "dates":        all_dates,
        "series":       series,
        "normalize":    norm,
        "filter_label": " | ".join(filter_parts),
    })


@app.get("/api/resources", response_class=JSONResponse)
def get_resources(start: str = None, end: str = None, receptors: str = None, status: str = "all", normalize: str = "0"):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)
    norm     = normalize == "1"

    df_api = _cached_api()
    df_api = _filter_by_date(df_api, dt_start, dt_end)
    if df_api.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    df = df_api[df_api["api"] == RESOURCES_API].copy()
    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    if sel:
        top_reps = [r for r in sel if r in df["receptor"].values]
    else:
        df_cons = _filter_by_date(_cached_consents(), dt_start, dt_end)
        base = df_cons if not df_cons.empty else df
        top_reps = [r for r in _top10_with_bradesco(base) if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_reps)]
    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    totals = df.groupby("receptor")["total"].sum().reindex(top_reps).fillna(0)
    values = totals.values.astype(float)

    if norm:
        df_cons = _filter_by_date(_cached_consents(), dt_start, dt_end)
        ct = df_cons.groupby("receptor")["total"].sum() if not df_cons.empty else pd.Series(dtype=float)
        for i, rec in enumerate(totals.index):
            n = float(ct.get(rec, 0))
            if n > 0:
                # Converte de Semanal para Mensal (30 dias)
                values[i] = (values[i] / n) / 7 * 30

    colors_map = _build_color_map(list(totals.index))
    
    # Organiza do maior para o menor
    combined = sorted(zip(list(totals.index), values.tolist()), key=lambda x: x[1], reverse=True)
    sorted_receptors = [c[0] for c in combined]
    sorted_values = [c[1] for c in combined]
    sorted_colors = [colors_map.get(r, "#4A9EFF") for r in sorted_receptors]

    return JSONResponse({
        "receptors": sorted_receptors,
        "values":    sorted_values,
        "colors":    sorted_colors,
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
