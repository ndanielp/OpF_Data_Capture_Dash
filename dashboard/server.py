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
from functools import wraps
from pathlib import Path

import pandas as pd
from cachetools import TTLCache
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
from services.constants import (
    API_GROUPS as _SHARED_API_GROUPS,
    BRAND_COLORS as _SHARED_BRAND,
    RESOURCES_API,
    EXCLUDED_APIS,
)

# ── Agrupamentos e Cores ───────────────────────────────────────────────────────
# Exposed as API_GROUPS[label] -> list[str] of api ids (flat shape for this
# module's heatmap code). The canonical source (with colors) lives in
# services.constants — imported above.
API_GROUPS: dict[str, list[str]] = {
    label: [a for a in info["apis"] if a != "customers"]  # ecossistema splits "customers" into customers-pf/pj
    for label, info in _SHARED_API_GROUPS.items()
}
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

_BRAND = _SHARED_BRAND

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

def _db_con() -> sqlite3.Connection:
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute("PRAGMA cache_size = -4096")   # limita page cache do SQLite a 4 MB
    # WAL + mmap + memory temp: read-only dashboard talks to a DB that the
    # collector writes in WAL mode; setting here lets queries stream pages
    # through mmap instead of syscalls, and keeps temp tables off disk.
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA mmap_size = 268435456")
    con.execute("PRAGMA temp_store = MEMORY")
    return con

def _load_consents(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    try:
        con = _db_con()
        if start and end:
            df = pd.read_sql(
                "SELECT date, receptor, total, cpf, cnpj FROM unique_consents"
                " WHERE date BETWEEN ? AND ?",
                con, params=[start.isoformat(), end.isoformat()], parse_dates=["date"],
            )
        else:
            df = pd.read_sql(
                "SELECT receptor, SUM(total) AS total, SUM(cpf) AS cpf, SUM(cnpj) AS cnpj"
                " FROM unique_consents GROUP BY receptor",
                con,
            )
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

def _load_api_with_endpoints(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Carrega api_requests com detalhe de endpoint, filtrado por data no SQL.
    A API 'customers' é dividida em 'customers-pf' / 'customers-pj' pelo
    label do endpoint, e os labels são normalizados para nomes curtos.
    """
    try:
        con = _db_con()
        if start and end:
            where  = "WHERE endpoint_id <> 0 AND date BETWEEN ? AND ?"
            params = [start.isoformat(), end.isoformat()]
        else:
            where  = "WHERE endpoint_id <> 0"
            params = None
        df = pd.read_sql(
            f"""SELECT date, receptor, api, endpoint_id, endpoint, status, SUM(total) AS total
                FROM api_requests {where}
                GROUP BY date, receptor, api, endpoint_id, endpoint, status""",
            con, params=params, parse_dates=["date"],
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

def _load_api(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Agrega api_requests por (date, receptor, api, status); customers já dividido em PF/PJ."""
    df = _load_api_with_endpoints(start, end)
    if df.empty:
        return df
    return df.groupby(["date", "receptor", "api", "status"], as_index=False)["total"].sum()


# ── Cache de janela limitada ───────────────────────────────────────────────────
# Cobre as últimas 52 semanas com dtypes compactos (category).
# Memória estimada: ~5 MB DataFrame + ~150 MB baseline Python ≪ 512 MB.
# Requests fora da janela (histórico antigo) caem no SQL direto,
# que é rápido graças ao covering index idx_api_dash_covering.

_CACHE_WEEKS = 52
_CACHE_TTL   = 300   # segundos entre recargas automáticas
_CACHE: dict = {"consents": None, "api": None, "ts": 0.0, "cutoff": None}
_CACHE_LOCK  = threading.Lock()

# Response-level cache for hot dashboard endpoints. TTL is short (60s) —
# long enough to absorb repeated refreshes from the same user during a
# typical filter-tweak session, short enough that fresh data surfaces fast.
_RESP_CACHE: TTLCache = TTLCache(maxsize=512, ttl=60)
_RESP_LOCK: threading.Lock = threading.Lock()


def cached_response(name: str):
    """Cache an endpoint's serialized JSON body by (name, query params).

    A hit skips re-computation and re-serialization. All dashboard query
    params are scalar (str/int/None), so frozenset of items is hashable.
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(**kwargs):
            key = (name, frozenset(kwargs.items()))
            with _RESP_LOCK:
                hit = _RESP_CACHE.get(key)
            if hit is not None:
                return Response(content=hit, media_type="application/json")
            resp = fn(**kwargs)
            if isinstance(resp, JSONResponse):
                with _RESP_LOCK:
                    _RESP_CACHE[key] = resp.body
            return resp
        return wrapper
    return deco


def _refresh_cache(force: bool = False) -> None:
    """Recarrega o cache. Thread-safe; chamado em background no startup."""
    with _CACHE_LOCK:
        if not force and _time.time() - _CACHE["ts"] < _CACHE_TTL:
            return
        cutoff = date.today() - timedelta(weeks=_CACHE_WEEKS)
        try:
            con = _db_con()
            df_cons = pd.read_sql(
                "SELECT date, receptor, total, cpf, cnpj FROM unique_consents"
                " WHERE date >= ?",
                con, params=[cutoff.isoformat()], parse_dates=["date"],
            )
            if not df_cons.empty:
                df_cons["receptor"] = df_cons["receptor"].astype("category")

            df_api = pd.read_sql(
                """SELECT date, receptor, api, endpoint_id, endpoint, status, SUM(total) AS total
                   FROM api_requests
                   WHERE endpoint_id <> 0 AND date >= ?
                   GROUP BY date, receptor, api, endpoint_id, endpoint, status""",
                con, params=[cutoff.isoformat()], parse_dates=["date"],
            )
            if not df_api.empty:
                for col in ("receptor", "api", "endpoint"):
                    df_api[col] = df_api[col].astype("category")

            con.close()
            _CACHE["consents"] = df_cons
            _CACHE["api"]      = df_api
            _CACHE["ts"]       = _time.time()
            _CACHE["cutoff"]   = cutoff
        except Exception:
            pass   # mantém cache anterior intacto em caso de erro


def _within_cache(start: date | None) -> bool:
    """True se o intervalo solicitado está coberto pelo cache atual."""
    cutoff = _CACHE.get("cutoff")
    return cutoff is not None and (start is None or start >= cutoff)


def _get_consents(start: date | None, end: date | None) -> pd.DataFrame:
    _refresh_cache()
    if _within_cache(start) and _CACHE["consents"] is not None:
        df = _CACHE["consents"]
        if start and end:
            mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
            return df[mask]
        return df
    return _load_consents(start, end)


def _get_api_ep(start: date | None, end: date | None) -> pd.DataFrame:
    _refresh_cache()
    if _within_cache(start) and _CACHE["api"] is not None:
        df = _CACHE["api"]
        if start and end:
            mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
            return df[mask]
        return df
    return _load_api_with_endpoints(start, end)


def _get_api(start: date | None, end: date | None) -> pd.DataFrame:
    """Versão agregada de _get_api_ep (soma por date/receptor/api/status)."""
    df = _get_api_ep(start, end)
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

def _ensure_dashboard_indexes() -> None:
    """Compound covering index the dashboard's consents queries need.

    The collector's scrapers.py ships single-column indexes; without this,
    queries filtered by (date, receptor_uuid) fall back to seek + row fetch.
    Wait up to 3s if the collector holds a write lock rather than crash.
    """
    try:
        con = _db_con()
        try:
            con.execute("PRAGMA busy_timeout = 3000")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_consents_date_rec "
                "ON unique_consents(date, receptor_uuid, total)"
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def _ensure_api_group_weekly():
    """Cria e popula api_group_weekly se vazio — compatibilidade com DBs antigos."""
    con = sqlite3.connect(str(config.DB_PATH))
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS api_group_weekly (
                date           TEXT    NOT NULL,
                receptor_uuid  TEXT    NOT NULL,
                receptor       TEXT    NOT NULL DEFAULT '',
                grp            TEXT    NOT NULL,
                req_week       INTEGER NOT NULL DEFAULT 0,
                consents_total INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date, receptor_uuid, grp))
        """)
        n = con.execute("SELECT COUNT(*) FROM api_group_weekly").fetchone()[0]
        if n == 0:
            con.executescript("""
                INSERT INTO api_group_weekly
                    (date, receptor_uuid, receptor, grp, req_week, consents_total)
                SELECT r.date, r.receptor_uuid, r.receptor,
                       CASE WHEN r.api='accounts' THEN 'Conta'
                            WHEN r.api='credit-cards-accounts' THEN 'Cartao'
                            WHEN r.api IN ('bank-fixed-incomes','credit-fixed-incomes',
                                'variable-incomes','funds','treasure-titles') THEN 'Investimento'
                            WHEN r.api IN ('loans','financings','invoice-financings',
                                'unarranged-accounts-overdraft') THEN 'Credito'
                            WHEN r.api='exchanges' THEN 'Cambio'
                            WHEN r.api='customers' THEN 'Identidade'
                       END AS grp,
                       SUM(r.total), c.total
                FROM api_requests r
                JOIN unique_consents c ON r.date=c.date AND r.receptor_uuid=c.receptor_uuid
                WHERE r.api NOT IN ('consents','resources') AND r.status=200
                GROUP BY r.date, r.receptor_uuid, grp HAVING grp IS NOT NULL;
            """)
    finally:
        con.close()


def _get_latest_weeks(n: int) -> list[str]:
    """Retorna as N datas mais recentes em api_requests com status=200, preenchendo até n."""
    con = sqlite3.connect(str(config.DB_PATH))
    try:
        rows = con.execute(
            "SELECT DISTINCT date FROM api_requests WHERE status=200 ORDER BY date DESC LIMIT ?",
            (n,),
        ).fetchall()
    finally:
        con.close()
    weeks = [r[0] for r in rows]
    while len(weeks) < n:
        weeks.append(weeks[-1] if weeks else "1900-01-01")
    return weeks


def _warm_profile_cache() -> None:
    """Pré-carrega dados institution-independent nos TTLCaches de of_analytics."""
    try:
        of_analytics._get_strategic_map("2024-01-01", "2100-01-01")
    except Exception:
        pass
    try:
        of_analytics._get_ecosystem_rankings("2024-01-01", "2100-01-01")
    except Exception:
        pass
    try:
        weeks = _get_latest_weeks(4)
        of_analytics._get_ep_ecosystem_stats(*weeks)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Garante que api_group_weekly exista e tenha dados (DBs antigos sem a tabela populada).
    _ensure_api_group_weekly()
    _ensure_dashboard_indexes()
    # Pré-aquece cache em background — servidor aceita conexões imediatamente.
    threading.Thread(target=lambda: _refresh_cache(force=True), daemon=True).start()
    threading.Thread(target=_warm_profile_cache, daemon=True).start()
    yield

from routers import openfinance
import services.of_analytics as of_analytics

app = FastAPI(title="OPF Batch Dashboard", lifespan=lifespan)
app.include_router(openfinance.router, prefix="/api/of")

GUI_DIR = Path(__file__).parent / "gui"

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = GUI_DIR / "dashboard.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.get("/profile", response_class=HTMLResponse)
async def profile():
    index_path = GUI_DIR / "receptor_profile.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.get("/api/receptors", response_class=JSONResponse)
@cached_response("receptors")
def get_receptors():
    # Consulta leve: apenas totais agregados por receptor, sem filtro de data
    df = _load_consents()   # sem datas → retorna GROUP BY receptor (sem coluna date)
    if df.empty: return JSONResponse([])
    all_recs = df.sort_values("total", ascending=False)["receptor"].tolist()
    colors = _build_color_map(all_recs)
    top10 = set(_top10_with_bradesco(df))
    return JSONResponse([
        {"label": r, "color": colors.get(r, "#4A5270"), "top": r in top10}
        for r in all_recs
    ])


@app.get("/api/consents", response_class=JSONResponse)
@cached_response("consents")
def get_consents(start: str = None, end: str = None, receptors: str = None):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)

    df = _get_consents(dt_start, dt_end)
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
@cached_response("api-requests")
def get_api_requests(start: str = None, end: str = None, receptors: str = None, status: str = "all", normalize: str = "0"):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)
    norm     = normalize == "1"

    # Carrega apenas o intervalo de datas solicitado — via cache ou SQL com índice
    _df_ep_full = _get_api_ep(dt_start, dt_end)
    df_api = (
        _df_ep_full.groupby(["date", "receptor", "api", "status"], as_index=False)["total"].sum()
        if not _df_ep_full.empty else pd.DataFrame()
    )
    if df_api.empty:
        return JSONResponse({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    df = df_api[~df_api["api"].isin(EXCLUDED_APIS | {RESOURCES_API})].copy()
    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    if df.empty:
        return JSONResponse({"groups": [], "apis": [], "receptors": [], "values": [], "max_val": 0})

    # Buscar df_cons UMA VEZ — reutilizado em top_reps, normalização heatmap e normalização endpoint
    df_cons = _get_consents(dt_start, dt_end) if (not sel or norm) else pd.DataFrame()

    if sel:
        top_reps = [r for r in sel if r in df["receptor"].values]
    else:
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
    ct_total = ct_cpf = ct_cnpj = pd.Series(dtype=float)  # populados abaixo se norm

    if norm:
        if not df_cons.empty:
            ct_total = df_cons.groupby("receptor")["total"].sum()
            ct_cpf   = df_cons.groupby("receptor")["cpf"].sum()
            ct_cnpj  = df_cons.groupby("receptor")["cnpj"].sum()
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
    df_ep = _df_ep_full  # já filtrado por data na leitura acima
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
                apis_arr = ep_pivot["api"].to_numpy()
                recs_arr = ep_pivot["receptor"].to_numpy()
                is_pf = pd.Series(apis_arr).isin(_NORM_CPF_APIS).to_numpy()
                is_pj = pd.Series(apis_arr).isin(_NORM_CNPJ_APIS).to_numpy()
                denoms = ct_total.reindex(recs_arr).to_numpy(dtype=float, na_value=0.0)
                if is_pf.any():
                    denoms[is_pf] = ct_cpf.reindex(recs_arr[is_pf]).to_numpy(dtype=float, na_value=0.0)
                if is_pj.any():
                    denoms[is_pj] = ct_cnpj.reindex(recs_arr[is_pj]).to_numpy(dtype=float, na_value=0.0)
                totals = ep_pivot["total"].to_numpy(dtype=float)
                safe = denoms > 0
                out = totals.copy()
                out[safe] = (totals[safe] / denoms[safe]) / 7.0 * 30.0
                out[~safe] = 0.0
                ep_pivot["total"] = out

            # Dict O(1) para lookup (api, receptor, endpoint_id) → total
            ep_dict: dict = (
                ep_pivot.set_index(["api", "receptor", "endpoint_id"])["total"]
                .to_dict()
            )

            for api_id in ordered_cols:
                api_rows = ep_pivot[ep_pivot["api"] == api_id]
                if api_rows.empty:
                    continue
                # Headers: endpoint_ids únicos ordenados por id
                ep_headers_df = (
                    api_rows[["endpoint_id", "endpoint"]]
                    .drop_duplicates()
                    .sort_values("endpoint_id")
                )
                headers = [{"id": int(r["endpoint_id"]), "label": r["endpoint"]}
                           for _, r in ep_headers_df.iterrows()]
                ep_ids = [h["id"] for h in headers]
                # Valores: [receptor][endpoint] — lookup O(1) por (api, receptor, endpoint_id)
                values_ep = [
                    [float(ep_dict.get((api_id, rec, ep_id), 0.0)) for ep_id in ep_ids]
                    for rec in top_reps
                ]
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
@cached_response("api-requests-timeseries")
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

    df = _get_api_ep(dt_start, dt_end)
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
        df_cons = _get_consents(dt_start, dt_end)
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
@cached_response("resources")
def get_resources(start: str = None, end: str = None, receptors: str = None, status: str = "all", normalize: str = "0"):
    today = date.today()
    dt_start = _parse_date(start, today - timedelta(days=365))
    dt_end   = _parse_date(end, today)
    sel      = _parse_receptors(receptors)
    norm     = normalize == "1"

    df_api = _get_api(dt_start, dt_end)
    if df_api.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    df = df_api[df_api["api"] == RESOURCES_API].copy()
    if status == "200": df = df[df["status"] == 200]
    elif status == "500": df = df[df["status"] == 500]

    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    df_cons = _get_consents(dt_start, dt_end) if (not sel or norm) else pd.DataFrame()

    if sel:
        top_reps = [r for r in sel if r in df["receptor"].values]
    else:
        base = df_cons if not df_cons.empty else df
        top_reps = [r for r in _top10_with_bradesco(base) if r in df["receptor"].values]

    df = df[df["receptor"].isin(top_reps)]
    if df.empty: return JSONResponse({"receptors": [], "values": [], "colors": []})

    totals = df.groupby("receptor")["total"].sum().reindex(top_reps).fillna(0)
    values = totals.values.astype(float)

    if norm:
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
@cached_response("stats")
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
