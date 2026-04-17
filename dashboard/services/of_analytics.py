
import hashlib
import threading
from datetime import datetime
import sqlite3
import statistics
from collections import defaultdict
from cachetools import TTLCache, cached
import config
from services.constants import API_GROUPS, API_LABELS, DB_GROUP_TO_DISPLAY, BRAND_COLORS

LABEL_MAP = {
    "ITAÚ UNIBANCO": "Itaú Unibanco", "CAIXA ECONOMICA FEDERAL": "Caixa Econômica Federal",
    "BANCO DO BRASIL": "Banco do Brasil", "MERCADO PAGO": "Mercado Pago",
    "SANTANDER BRASIL": "Santander Brasil", "BRADESCO": "Bradesco", "NUBANK": "Nubank",
}

AVATAR_MAP = {"BRADESCO":"BDC","NUBANK":"NU","ITAÚ UNIBANCO":"ITÁ","BANCO DO BRASIL":"BB","CAIXA ECONOMICA FEDERAL":"CEF","MERCADO PAGO":"MP","SANTANDER BRASIL":"SAN"}

def _brand_color(receptor_name: str) -> str | None:
    """Substring lookup against the canonical BRAND_COLORS list (shared with Ecossistema)."""
    name = (receptor_name or "").lower()
    for key, color in BRAND_COLORS:
        if key in name:
            return color
    return None

def avatar_color_fallback(institution_id: str) -> str:
    h = int(hashlib.md5(institution_id.encode()).hexdigest()[:4], 16)
    return f"hsl({h % 360}, 60%, 40%)"

def fmt_req(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.1f} Bi".replace(".", ",")
    if n >= 1_000_000: return f"{n/1_000_000:.1f} Mi".replace(".", ",")
    return f"{n:,}".replace(",", ".")

def fmt_period(first: str, last: str) -> str:
    if not first or not last: return "N/A"
    try:
        def abbr(d): return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%b/%y").capitalize()
        return f"{abbr(first)} – {abbr(last)}"
    except: return f"{first} - {last}"

def fmt_consents(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.2f} Mi".replace(".", ",")
    if n >= 1_000: return f"{n/1_000:.1f} k".replace(".", ",")
    return str(n)

def get_institutions():
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    # Retorna apenas receptores com volume real em api_requests (status 200)
    # ordenados por volume total descendente
    cur.execute("""
        SELECT receptor_uuid AS id, receptor AS name, SUM(total) AS vol
        FROM api_requests
        WHERE receptor_uuid IS NOT NULL
          AND status = 200
          AND api NOT IN ('consents', 'resources')
        GROUP BY receptor_uuid, receptor
        HAVING vol > 0
        ORDER BY vol DESC
    """)
    rows = cur.fetchall()
    con.close()
    institutions = []
    seen = set()
    for row in rows:
        db_id = row["id"]
        if db_id in seen:
            continue
        seen.add(db_id)
        institutions.append({
            "id": db_id,
            "label": LABEL_MAP.get(row["name"], row["name"].title()),
            "uuid": db_id
        })
    return institutions

def _get_consents(row) -> float:
    ep = row["endpoint"].lower()
    keys = row.keys()
    cpf_val = row["cpf"] if "cpf" in keys else row["consents_cpf"]
    cnpj_val = row["cnpj"] if "cnpj" in keys else row["consents_cnpj"]
    if "jurídica" in ep or "juridica" in ep: return float(cnpj_val or 0)
    if "natural" in ep: return float(cpf_val or 0)
    return float(row["consents_total"] or 0)

def normalize(req_week: float, consents: float, days: int = 30) -> float:
    if consents <= 0: return 0.0
    return (req_week / consents) * (days / 7)

_SQL_EP_INSTITUTION = """
SELECT r.api, r.endpoint,
       SUM(r.total)  AS req_4w,
       AVG(c.total)  AS avg_c_total,
       AVG(c.cpf)    AS avg_c_cpf,
       AVG(c.cnpj)   AS avg_c_cnpj
FROM api_requests r
JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
WHERE r.receptor_uuid = :institution
  AND r.api NOT IN ('consents', 'resources')
  AND r.status = 200
  AND r.endpoint_id <> 0
  AND r.date IN (:w1, :w2, :w3, :w4)
GROUP BY r.api, r.endpoint
ORDER BY r.api, SUM(r.total) DESC
"""

_SQL_EP_ECOSYSTEM = """
SELECT r.receptor_uuid AS receptor, r.api, r.endpoint,
       SUM(r.total)  AS req_4w,
       AVG(c.total)  AS avg_c_total,
       AVG(c.cpf)    AS avg_c_cpf,
       AVG(c.cnpj)   AS avg_c_cnpj
FROM api_requests r
JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
WHERE r.api NOT IN ('consents', 'resources')
  AND r.status = 200
  AND r.endpoint_id <> 0
  AND r.date IN (:w1, :w2, :w3, :w4)
GROUP BY r.receptor_uuid, r.api, r.endpoint
"""


def _ep_consents(ep_name: str, avg_total, avg_cpf, avg_cnpj) -> float:
    ep_l = ep_name.lower()
    if "jurídica" in ep_l or "juridica" in ep_l:
        return float(avg_cnpj or 0)
    if "natural" in ep_l:
        return float(avg_cpf or 0)
    return float(avg_total or 0)


def _ep_intensity(req_4w: float, consents: float) -> float:
    return round(normalize(req_4w / 4.0, consents, 30), 5)


_ep_eco_cache = TTLCache(maxsize=8, ttl=3600)
_ep_eco_lock  = threading.Lock()

@cached(cache=_ep_eco_cache, lock=_ep_eco_lock)
def _get_ep_ecosystem_stats(w1: str, w2: str, w3: str, w4: str) -> dict:
    """Estatísticas do ecossistema para endpoint depth — invariante por conjunto de 4 semanas.

    Cacheado por LRU: múltiplas chamadas com o mesmo ep_weeks (instituições diferentes
    no mesmo período) reutilizam o resultado sem repetir o scan completo.
    """
    params = {"w1": w1, "w2": w2, "w3": w3, "w4": w4}
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        eco_rows = con.execute(_SQL_EP_ECOSYSTEM, params).fetchall()
    finally:
        con.close()
    eco_vals: dict = defaultdict(list)
    for row in eco_rows:
        api, ep = row["api"], row["endpoint"]
        if api == "customers":
            is_pj = "jurídica" in ep.lower() or "juridica" in ep.lower()
            cu = float(row["avg_c_cnpj"] or 0) if is_pj else float(row["avg_c_cpf"] or 0)
        else:
            cu = _ep_consents(ep, row["avg_c_total"], row["avg_c_cpf"], row["avg_c_cnpj"])
        val = _ep_intensity(float(row["req_4w"]), cu)
        if val > 0:
            eco_vals[f"{api}|||{ep}"].append(val)
    result: dict = {}
    for key, vals in eco_vals.items():
        sv = sorted(vals)
        n  = len(sv)
        if n < 2:
            continue
        upper = sv[n - n // 2:]
        result[key] = {"median": round(statistics.median(sv), 4), "q3": round(statistics.median(upper), 4)}
    return result


def get_endpoint_depth(institution: str, from_date: str = "2000-01-01", to_date: str = "2100-01-01", normalize: bool = True) -> dict:
    """Retorna profundidade de consumo por endpoint para a instituição e estatísticas do ecossistema."""
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        ep_rows = con.execute(
            "SELECT DISTINCT date FROM api_requests "
            "WHERE status=200 AND receptor_uuid=? AND date>=? AND date<=? ORDER BY date DESC LIMIT 4",
            (institution, from_date, to_date),
        ).fetchall()
        ep_weeks = [r["date"] for r in ep_rows]
        if not ep_weeks:
            return {"institution_endpoints": {}, "ecosystem_stats": {}}
        padded = list(ep_weeks)
        while len(padded) < 4:
            padded.append(padded[-1])
        params = {
            "w1": padded[0], "w2": padded[1], "w3": padded[2], "w4": padded[3],
            "institution": institution,
        }
        inst_rows = con.execute(_SQL_EP_INSTITUTION, params).fetchall()
    finally:
        con.close()

    # ── 1. Intensidades da instituição ──────────────────────────────────
    def _ep_value(req_4w: float, consents: float) -> float:
        if normalize:
            return _ep_intensity(req_4w, consents)
        return round(req_4w / 4.0, 1)  # média semanal bruta

    institution_endpoints: dict = {}
    _cust_req_total   = 0.0
    _cust_avg_c_total = 0.0
    for row in inst_rows:
        api = row["api"]
        ep  = row["endpoint"]
        if api == "customers":
            ep_l = ep.lower()
            sub  = "pj" if ("jurídica" in ep_l or "juridica" in ep_l) else "pf"
            cu   = float(row["avg_c_cnpj"] or 0) if sub == "pj" else float(row["avg_c_cpf"] or 0)
            _cust_req_total   += float(row["req_4w"])
            _cust_avg_c_total  = float(row["avg_c_total"] or 0)
        else:
            cu = _ep_consents(ep, row["avg_c_total"], row["avg_c_cpf"], row["avg_c_cnpj"])
        val = _ep_value(float(row["req_4w"]), cu)

        if api == "customers":
            institution_endpoints.setdefault("customers", {"pf": {}, "pj": {}})
            institution_endpoints["customers"][sub][ep] = val
        else:
            institution_endpoints.setdefault(api, {})
            institution_endpoints[api][ep] = val

    if "customers" in institution_endpoints:
        institution_endpoints["customers"]["api_intensity"] = \
            _ep_value(_cust_req_total, _cust_avg_c_total)

    # ── 2. Estatísticas do ecossistema (cacheadas por conjunto de semanas) ──
    ecosystem_stats = _get_ep_ecosystem_stats(*padded)

    return {
        "institution_endpoints": institution_endpoints,
        "ecosystem_stats":       ecosystem_stats,
    }


def get_ecosystem_stats():
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT r.date, r.receptor_uuid AS receptor, r.api, r.endpoint,
               SUM(r.total) AS req_week, c.cpf, c.cnpj, c.total AS consents_total
        FROM api_requests r
        JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
        WHERE r.api NOT IN ('consents', 'resources') AND r.status = 200
        GROUP BY r.date, r.receptor_uuid, r.api, r.endpoint
    """)
    rows = cur.fetchall()
    con.close()
    data = defaultdict(lambda: defaultdict(list))
    for row in rows:
        c = _get_consents(row)
        if c > 0:
            data[f"{row['api']}|||{row['endpoint']}"][row["receptor"]].append(normalize(row["req_week"], c, 30))
    stats = {}
    for key, receptor_weeks in data.items():
        receptor_means = [sum(w)/len(w) for w in receptor_weeks.values() if len(w) > 0]
        if len(receptor_means) < 2: continue
        receptor_means_sorted = sorted(receptor_means)
        n = len(receptor_means_sorted)
        stats[key] = {"median": round(statistics.median(receptor_means_sorted), 4), "q3": round(statistics.median(receptor_means_sorted[n - n // 2:]), 4)}
    return {"stats": stats, "receptor_count": len({row["receptor"] for row in rows})}

_eco_rankings_cache = TTLCache(maxsize=8, ttl=3600)
_eco_rankings_lock  = threading.Lock()

@cached(cache=_eco_rankings_cache, lock=_eco_rankings_lock)
def _get_ecosystem_rankings(from_date: str, to_date: str) -> list[dict]:
    """Rankings globais (err_rate, n_transmitters, vol_req) por receptor — institution-independent.

    Cacheado por (from_date, to_date): idêntico para qualquer instituição no mesmo período,
    evitando o full-scan de api_requests a cada load de perfil.
    """
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT receptor_uuid, "
            "SUM(CASE WHEN status=500 THEN total ELSE 0 END)*1.0/SUM(total) AS err_rate, "
            "COUNT(DISTINCT transmitter_uuid) AS n_transmitters, "
            "SUM(CASE WHEN status=200 THEN total ELSE 0 END) AS vol_req "
            "FROM api_requests WHERE date>=? AND date<=? GROUP BY receptor_uuid",
            (from_date, to_date),
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def classify_archetype(c: dict):
    if c.get("Empréstimos", 0) > 0.45: return "FOCO EM CRÉDITO", "Consumo dominado por APIs de crédito."
    if c.get("Investimentos", 0) > 0.40: return "FOCO EM INVESTIMENTOS", "Consumo concentrado em renda fixa, variável e fundos."
    if c.get("Contas", 0) > 0.50: return "FOCO EM CONTA CORRENTE", "Consumo predominante de dados de conta."
    if c.get("Empréstimos", 0) > 0.30 and c.get("Contas", 0) > 0.25: return "CRÉDITO & CONTA", "Mix equilibrado."
    if c.get("Investimentos", 0) > 0.25 and c.get("Empréstimos", 0) > 0.25: return "CRÉDITO & INVEST", "Combinação relevante."
    if c.get("Cadastro", 0) > 0.30: return "FOCO EM IDENTIDADE", "Alta proporção cadastral."
    return "PERFIL DIVERSIFICADO", "Consumo distribuído."

# Note: classify_archetype keys must match API_GROUPS names in services.constants
# (used by get_profile_header when computing category_shares via group_info["apis"]).

def get_profile_header(institution: str, from_date: str = "2000-01-01", to_date: str = "2100-01-01") -> dict | None:
    """KPIs, rankings, archetype, summary e period. ~8 queries rápidas, todas indexadas por receptor_uuid."""
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1. Total Reqs + datas do período
    cur.execute("SELECT SUM(total) AS total_req, MIN(date) AS first_date, MAX(date) AS last_date FROM api_requests WHERE receptor_uuid = ? AND status = 200 AND date >= ? AND date <= ?", (institution, from_date, to_date))
    kpi1 = cur.fetchone()
    # 2. Consents — snapshot mais recente e primeiro dentro do período
    cur.execute("SELECT total AS current_consents, date AS current_date FROM unique_consents WHERE receptor_uuid = ? AND date <= ? ORDER BY date DESC LIMIT 1", (institution, to_date))
    kpi2_curr = cur.fetchone()
    cur.execute("SELECT total AS first_consents FROM unique_consents WHERE receptor_uuid = ? AND date >= ? ORDER BY date ASC LIMIT 1", (institution, from_date))
    kpi2_first = cur.fetchone()

    # 3. Rankings globais — cacheados por período, institution-independent
    all_ranks = _get_ecosystem_rankings(from_date, to_date)

    err_sorted = sorted([x for x in all_ranks if x["err_rate"] is not None], key=lambda x: x["err_rate"])
    tx_sorted = sorted([x for x in all_ranks if x["n_transmitters"] is not None], key=lambda x: x["n_transmitters"], reverse=True)
    vol_sorted = sorted([x for x in all_ranks if x["vol_req"] is not None], key=lambda x: x["vol_req"], reverse=True)

    total_reps = len(all_ranks)
    eco_avg_error = sum(x["err_rate"] for x in all_ranks if x["err_rate"] is not None) / total_reps if total_reps > 0 else 0

    def get_rank(l, k):
        for i, x in enumerate(l):
            if x["receptor_uuid"] == institution: return i+1
        return total_reps

    err_rank = get_rank(err_sorted, "err_rate")
    tx_rank  = get_rank(tx_sorted,  "n_transmitters")
    vol_rank = get_rank(vol_sorted,  "vol_req")

    my_err_rate = next((x["err_rate"] for x in all_ranks if x["receptor_uuid"] == institution), 0) or 0
    my_tx       = next((x["n_transmitters"] for x in all_ranks if x["receptor_uuid"] == institution), 0) or 0

    ordinals_pt = {1:"1º", 2:"2º", 3:"3º", 4:"4º", 5:"5º", 6:"6º", 7:"7º"}
    ext_ord = lambda r: ordinals_pt.get(r, f"{r}º")

    # 4. Intensity 30D
    cur.execute("SELECT MAX(r.date) AS ref_date FROM api_requests r JOIN unique_consents c ON r.date=c.date AND r.receptor_uuid=c.receptor_uuid WHERE r.receptor_uuid=? AND r.status=200 AND r.api NOT IN ('consents','resources') AND r.date >= ? AND r.date <= ?", (institution, from_date, to_date))
    ref_date_row = cur.fetchone()
    ref_date = ref_date_row["ref_date"] if ref_date_row else None

    intensity_30d = 0.0
    eco_median = 0.0
    if ref_date:
        cur.execute("SELECT SUM(r.total)*1.0/MAX(c.total)*(30.0/7) AS ints FROM api_requests r JOIN unique_consents c ON r.date=c.date AND r.receptor_uuid=c.receptor_uuid WHERE r.receptor_uuid=? AND r.date=? AND r.status=200 AND r.api NOT IN ('consents','resources')", (institution, ref_date))
        int_row = cur.fetchone()
        intensity_30d = int_row["ints"] or 0.0
        cur.execute("SELECT r.receptor_uuid, SUM(r.total)*1.0/MAX(c.total)*(30.0/7) AS ints FROM api_requests r JOIN unique_consents c ON r.date=c.date AND r.receptor_uuid=c.receptor_uuid WHERE r.date=? AND r.status=200 AND r.api NOT IN ('consents','resources') GROUP BY r.receptor_uuid", (ref_date,))
        eco_ints = [x["ints"] for x in cur.fetchall() if x["ints"] is not None]
        if eco_ints: eco_median = statistics.median(eco_ints)

    # 5. Nome da instituição
    cur.execute("SELECT receptor FROM unique_consents WHERE receptor_uuid = ? LIMIT 1", (institution,))
    rname = cur.fetchone()
    inst_name = rname["receptor"] if rname else institution
    inst_clean_name = LABEL_MAP.get(inst_name, inst_name.title())

    # 6. Totais por API — para category_shares e archetype
    cur.execute("SELECT api, SUM(total) AS total FROM api_requests WHERE receptor_uuid = :receptor AND api NOT IN ('consents','resources') AND status = 200 AND date >= :from_date AND date <= :to_date GROUP BY api", {"receptor": institution, "from_date": from_date, "to_date": to_date})
    inst_totals = {r["api"]: r["total"] for r in cur.fetchall()}

    if sum(inst_totals.values()) == 0:
        con.close()
        return None

    # 7. Contagem de semanas no período
    cur.execute("SELECT COUNT(DISTINCT date) AS wc FROM api_requests WHERE receptor_uuid=? AND status=200 AND date>=? AND date<=?", (institution, from_date, to_date))
    weeks_count = (cur.fetchone()["wc"] or 0)
    con.close()

    # Build KPIs
    bg_color = _brand_color(inst_name) or avatar_color_fallback(institution)
    header = {
        "avatar": {
            "initials": AVATAR_MAP.get(inst_name, "".join(w[0] for w in inst_clean_name.split())[:3].upper()),
            "background_color": bg_color,
            "text_color": "#1A1A2E" if bg_color.lower() == "#fbba00" else "#FFFFFF"
        },
        "archetype": "...",
        "kpis": {}
    }

    if kpi1 and kpi1["total_req"]:
        header["kpis"]["total_requests"] = {
            "value": kpi1["total_req"], "formatted": fmt_req(kpi1["total_req"]),
            "subtitle": fmt_period(kpi1["first_date"], kpi1["last_date"])
        }
    else: header["kpis"]["total_requests"] = {"value": 0, "formatted": "0", "subtitle": "N/A"}

    if kpi2_curr and kpi2_first and kpi2_first["first_consents"]:
        cg = (kpi2_curr["current_consents"] - kpi2_first["first_consents"]) / kpi2_first["first_consents"] * 100
        da = datetime.strptime(kpi2_curr["current_date"][:10], "%Y-%m-%d").strftime("%b/%y").capitalize()
        header["kpis"]["consents"] = {
            "formatted": fmt_consents(kpi2_curr["current_consents"]),
            "subtitle": f"{da} · +{cg:.0f}% no período" if cg >= 0 else f"{da} · {cg:.0f}% no período"
        }
    else: header["kpis"]["consents"] = {"formatted": "0", "subtitle": "N/A"}

    header["kpis"]["intensity_30d"] = {
        "formatted": f"~{int(round(intensity_30d))}",
        "subtitle": "req/consent/30d · últ. semana",
        "above_median": intensity_30d >= eco_median
    }

    tr = "green" if err_rank <= 2 else ("warning" if err_rank <= 4 else "error")
    header["kpis"]["error_rate"] = {
        "formatted": f"{my_err_rate*100:.2f}%".replace(".", ","),
        "subtitle": f"{ext_ord(err_rank)} melhor · ecossistema avg {eco_avg_error*100:.1f}%".replace(".", ","),
        "color_tier": tr
    }

    sub_tx = "Maior cobertura do ecossistema" if tx_rank == 1 else ("Menor cobertura do ecossistema" if tx_rank == total_reps else f"{ext_ord(tx_rank)} maior cobertura")
    header["kpis"]["transmitters"] = {
        "formatted": str(my_tx), "subtitle": sub_tx,
        "color_tier": "gold" if tx_rank == 1 else ("green" if tx_rank <= 3 else "neutral")
    }

    sub_vol = "Maior volume do ecossistema" if vol_rank == 1 else ("Menor volume absoluto" if vol_rank == total_reps else (f"{ext_ord(vol_rank)} maior volume" if vol_rank <= 3 else f"{ext_ord(vol_rank)} de {total_reps}"))
    tv = "gold" if vol_rank == 1 else ("green" if vol_rank <= 3 else ("warning" if vol_rank >= total_reps - 1 else "neutral"))
    header["kpis"]["volume_rank"] = {
        "formatted": f"#{vol_rank} / {total_reps}", "subtitle": sub_vol, "color_tier": tv
    }

    inst_total_all = sum(inst_totals.values())
    category_shares = {}
    for group_name, group_info in API_GROUPS.items():
        g_inst = sum(inst_totals.get(a, 0) for a in group_info["apis"])
        category_shares[group_name] = g_inst / inst_total_all if inst_total_all > 0 else 0

    archetype_name, archetype_desc = classify_archetype(category_shares)
    header["archetype"] = archetype_name

    return {
        "institution": {"id": institution, "label": inst_clean_name, "uuid": institution, "archetype": archetype_name, "archetype_description": archetype_desc},
        "header": header,
        "summary": {
            "total_consents": kpi2_curr["current_consents"] if kpi2_curr else 0,
            "active_apis":    len(inst_totals),
            "weeks_count":    weeks_count,
        },
        "period": {
            "from":        kpi1["first_date"] or from_date,
            "to":          kpi1["last_date"]  or to_date,
            "weeks_count": weeks_count,
        },
    }


def get_tornado_data(institution: str, from_date: str = "2000-01-01", to_date: str = "2100-01-01", normalize: bool = True) -> dict:
    """Wrapper público para _get_tornado_data — abre sua própria conexão."""
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT receptor FROM unique_consents WHERE receptor_uuid = ? LIMIT 1", (institution,))
    rname = cur.fetchone()
    inst_name = rname["receptor"] if rname else institution
    inst_clean_name = LABEL_MAP.get(inst_name, inst_name.title())
    result = _get_tornado_data(cur, institution, inst_clean_name, from_date, to_date, normalize)
    con.close()
    return result


_strategic_map_cache = TTLCache(maxsize=8, ttl=3600)
_strategic_map_lock  = threading.Lock()

@cached(cache=_strategic_map_cache, lock=_strategic_map_lock)
def _get_strategic_map(from_date: str, to_date: str, normalize: bool = True) -> dict:
    """Calcula o Mapa Estratégico para todos os receptores.

    normalize=True  → req / consentimento / 30d   (média das últimas 4 semanas)
    normalize=False → total de requisições no período filtrado (sem normalização)
    """
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    GROUPS = ["Conta", "Cartao", "Investimento", "Credito", "Cambio", "Identidade", "Resource"]
    _empty = {"reference_weeks": [], "all_receptors": {}, "group_stats": {}}

    receptor_vals: dict = defaultdict(lambda: defaultdict(float))  # label → grp → value
    receptor_labels: dict = {}

    if normalize:
        # ── Modo normalizado: média de TODAS as semanas do período ─────────
        cur.execute("""
            SELECT receptor_uuid, receptor, grp, req_week, consents_total, date
            FROM api_group_weekly
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, (from_date, to_date))
        rows = cur.fetchall()
        con.close()

        if not rows:
            return _empty

        # acumula intensidades semanais para fazer a média do período inteiro
        weekly: dict = defaultdict(lambda: defaultdict(list))
        all_dates: set = set()
        for row in rows:
            cons = float(row["consents_total"] or 0)
            req  = float(row["req_week"]       or 0)
            if cons <= 0:
                continue
            uid = row["receptor_uuid"]
            weekly[uid][row["grp"]].append((req / cons) * (30.0 / 7))
            all_dates.add(row["date"])
            if uid not in receptor_labels:
                receptor_labels[uid] = LABEL_MAP.get(row["receptor"], row["receptor"].title())

        for uid, groups in weekly.items():
            label = receptor_labels.get(uid, uid)
            for grp, vals in groups.items():
                receptor_vals[label][grp] = round(sum(vals) / len(vals), 2)

        sorted_dates = sorted(all_dates)
        reference_weeks = [sorted_dates[0], sorted_dates[-1]] if sorted_dates else []

    else:
        # ── Modo volume bruto: total de req no período filtrado ────────────
        cur.execute("""
            SELECT receptor_uuid, receptor, grp, SUM(req_week) AS total_req
            FROM api_group_weekly
            WHERE date >= ? AND date <= ?
            GROUP BY receptor_uuid, receptor, grp
        """, (from_date, to_date))
        rows = cur.fetchall()
        cur.execute("""
            SELECT MIN(date) AS first_w, MAX(date) AS last_w
            FROM api_group_weekly WHERE date >= ? AND date <= ?
        """, (from_date, to_date))
        wrange = cur.fetchone()
        con.close()

        if not rows:
            return _empty

        for row in rows:
            uid = row["receptor_uuid"]
            if uid not in receptor_labels:
                receptor_labels[uid] = LABEL_MAP.get(row["receptor"], row["receptor"].title())
            label = receptor_labels[uid]
            receptor_vals[label][row["grp"]] = round(float(row["total_req"] or 0), 0)

        reference_weeks = [wrange["first_w"], wrange["last_w"]] if wrange else []

    all_receptors = {label: dict(grps) for label, grps in receptor_vals.items()}

    # ── GROUP_STATS: mean, median, Q1, Q3, IQR, outlier_fence (Tukey) ──
    group_stats: dict = {}
    outliers:    dict = {}
    for grp in GROUPS:
        vals = sorted(all_receptors[rec].get(grp, 0.0) for rec in all_receptors)
        n = len(vals)
        if n == 0:
            group_stats[grp] = {"mean": 0, "median": 0, "q1": 0, "q3": 0, "iqr": 0, "outlier_fence": 0}
            outliers[grp] = []
            continue
        mean_v   = sum(vals) / n
        median_v = statistics.median(vals)
        lower    = vals[:n // 2]
        upper    = vals[n - n // 2:]
        q1_v     = statistics.median(lower) if lower else 0.0
        q3_v     = statistics.median(upper)
        iqr_v    = q3_v - q1_v
        fence_v  = q3_v + 1.5 * iqr_v
        group_stats[grp] = {
            "mean":          round(mean_v,   2),
            "median":        round(median_v, 2),
            "q1":            round(q1_v,     2),
            "q3":            round(q3_v,     2),
            "iqr":           round(iqr_v,    2),
            "outlier_fence": round(fence_v,  2),
        }
        if normalize:
            outliers[grp] = [
                {"label": rec, "value": round(all_receptors[rec][grp], 1)}
                for rec in all_receptors
                if all_receptors[rec].get(grp, 0.0) > fence_v
            ]
        else:
            outliers[grp] = []   # modo bruto: todos os pontos visíveis, sem triângulos

    if normalize:
        groups_with_outliers = [(g, group_stats[g]["outlier_fence"]) for g in GROUPS if outliers.get(g)]
        worst_case_group = max(groups_with_outliers, key=lambda t: t[1])[0] if groups_with_outliers else None
        non_outlier_vals = [
            all_receptors[rec].get(grp, 0.0)
            for grp in GROUPS
            for rec in all_receptors
            if all_receptors[rec].get(grp, 0.0) <= group_stats[grp]["outlier_fence"]
        ]
        x_cap = round(max(non_outlier_vals) * 1.05, 1) if non_outlier_vals else 500.0
    else:
        worst_case_group = None
        all_vals = [
            all_receptors[rec].get(grp, 0.0)
            for grp in GROUPS
            for rec in all_receptors
        ]
        x_cap = round(max(all_vals) * 1.05, 0) if all_vals else 1e9

    return {
        "reference_weeks":  reference_weeks,
        "all_receptors":    all_receptors,
        "group_stats":      group_stats,
        "outliers":         outliers,
        "worst_case_group": worst_case_group,
        "x_cap":            x_cap,
    }



def _get_tornado_data(cur, institution_uuid: str, inst_display_name: str,
                      from_date: str = "2000-01-01", to_date: str = "2100-01-01", normalize: bool = True) -> dict:
    """Calcula o fluxo bilateral de requisições entre a instituição (por UUID) e cada par."""
    # 1. Semanas dentro do período
    cur.execute("SELECT COUNT(DISTINCT date) AS n_weeks, MIN(date) AS min_date, MAX(date) AS max_date FROM api_requests WHERE status=200 AND date >= ? AND date <= ?", (from_date, to_date))
    meta = cur.fetchone()
    n_weeks = meta["n_weeks"] or 0
    if not n_weeks:
        return {"reference_weeks": [], "scale_max": 0, "left_label": "", "right_label": "", "rows": []}

    weeks = [meta["min_date"], meta["max_date"]]  # só para period_label
    norm = 30.0 / (n_weeks * 7.0) if normalize else 1.0

    # 2. LEFT: institution_uuid como receptor — ela consulta transmissores
    cur.execute("""
        SELECT transmitter AS institution_name, transmitter_uuid AS institution_uuid,
               SUM(total) * ? / 1e6 AS value_30d
        FROM api_requests
        WHERE receptor_uuid = ?
          AND status = 200
          AND api NOT IN ('consents', 'resources')
          AND date >= ? AND date <= ?
        GROUP BY transmitter, transmitter_uuid
    """, (norm, institution_uuid, from_date, to_date))
    left_rows = [dict(r) for r in cur.fetchall()]

    # 3. RIGHT: institution_uuid como transmissor — outros a consultam
    cur.execute("""
        SELECT receptor AS institution_name, receptor_uuid AS institution_uuid,
               SUM(total) * ? / 1e6 AS value_30d
        FROM api_requests
        WHERE transmitter_uuid = ?
          AND status = 200
          AND api NOT IN ('consents', 'resources')
          AND date >= ? AND date <= ?
        GROUP BY receptor, receptor_uuid
    """, (norm, institution_uuid, from_date, to_date))
    right_rows = [dict(r) for r in cur.fetchall()]

    # 4. Merge — chave de merge = institution_name (nome DB) ou institution_uuid
    # Usamos uuid como chave de merge para evitar ambiguidade de nomes
    left_map  = {r["institution_uuid"]: {"name": r["institution_name"], "val": r["value_30d"]} for r in left_rows}
    right_map = {r["institution_uuid"]: {"name": r["institution_name"], "val": r["value_30d"]} for r in right_rows}

    all_uuids = (set(left_map) | set(right_map)) - {institution_uuid}

    rows = []
    for uid in all_uuids:
        lv = left_map[uid]["val"]  if uid in left_map  else None
        rv = right_map[uid]["val"] if uid in right_map else None
        raw_name = (left_map.get(uid) or right_map.get(uid))["name"]
        rows.append({
            "institution_name": raw_name,
            "institution_uuid": uid,
            "label": LABEL_MAP.get(raw_name, raw_name.title()),
            "left":  round(lv, 1) if lv is not None else None,
            "right": round(rv, 1) if rv is not None else None,
            "total": round((lv or 0) + (rv or 0), 1),
            "bilateral": lv is not None and rv is not None,
        })

    rows.sort(key=lambda x: -x["total"])

    # 5. Corte: bilaterais + top unilaterais até MAX_ROWS=20
    bilateral  = [r for r in rows if r["bilateral"]]
    unilateral = [r for r in rows if not r["bilateral"]]
    MAX_ROWS = 20
    result_rows = bilateral + unilateral[:max(0, MAX_ROWS - len(bilateral))]
    result_rows.sort(key=lambda x: -x["total"])

    # 6. scale_max
    scale_max = max(
        (max(r["left"] or 0, r["right"] or 0) for r in result_rows),
        default=1.0
    )

    # Formatar período de referência
    if len(weeks) >= 2:
        def _abbr(d):
            return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d/%b/%y").lower()
        period_str = f"{_abbr(weeks[-1])} – {_abbr(weeks[0])}"
    else:
        period_str = weeks[0][:10] if weeks else ""

    return {
        "reference_weeks": weeks,
        "period_label": period_str,
        "scale_max": round(scale_max, 1),
        "left_label":  f"{inst_display_name} consulta",
        "right_label": f"consulta {inst_display_name}",
        "rows": result_rows,
    }


# ── Evolução Temporal ─────────────────────────────────────────────────────

_TEMPORAL_GROUPS = ['Conta', 'Cartao', 'Investimento', 'Credito', 'Cambio', 'Identidade', 'Resource']

def get_temporal_intensity(institution: str, from_date: str = "2000-01-01", to_date: str = "2100-01-01", normalize: bool = True) -> dict:
    """
    Retorna todas as semanas disponíveis para a instituição dentro do período:
      normalize=True  → {"2025-06-06": {"Conta": 61.11, ...}}  (req/consent/30d)
      normalize=False → {"2025-06-06": {"Conta": 12500, ...}}  (req_week bruto)
    Lê de api_group_weekly (pré-agregada) em vez do JOIN pesado em api_requests.
    """
    result: dict = {}
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("""
            SELECT date, grp, req_week, consents_total
            FROM api_group_weekly
            WHERE receptor_uuid = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (institution, from_date, to_date)).fetchall()
    finally:
        con.close()

    for row in rows:
        date = row["date"]
        grp  = row["grp"]
        req  = float(row["req_week"]      or 0)
        cons = float(row["consents_total"] or 0)
        if normalize:
            value = round((req / cons) * (30.0 / 7.0), 4) if cons > 0 else 0.0
        else:
            value = round(req, 0)
        if date not in result:
            result[date] = {g: 0.0 for g in _TEMPORAL_GROUPS}
        result[date][grp] = value

    return dict(sorted(result.items()))

