
import hashlib
import functools
from datetime import datetime
import sqlite3
import statistics
from collections import defaultdict
import config

API_GROUPS = {
    "Conta": {"color": "#4A9EFF", "apis": ["accounts", "credit-cards-accounts"]},
    "Crédito": {"color": "#FF6B6B", "apis": ["loans", "financings", "invoice-financings", "unarranged-accounts-overdraft"]},
    "Investimentos": {"color": "#2ECC7F", "apis": ["bank-fixed-incomes", "credit-fixed-incomes", "variable-incomes", "funds", "treasure-titles"]},
    "Identidade": {"color": "#F5A623", "apis": ["customers"]},
    "Câmbio": {"color": "#A855F7", "apis": ["exchanges"]},
}

API_LABELS = {
    "accounts": "Contas", "credit-cards-accounts": "Cartão de Crédito",
    "loans": "Empréstimos", "financings": "Financiamentos",
    "invoice-financings": "Financiamentos de Faturas", "unarranged-accounts-overdraft": "Cheque Especial",
    "bank-fixed-incomes": "Renda Fixa Bancária", "credit-fixed-incomes": "Renda Fixa Crédito",
    "variable-incomes": "Renda Variável", "funds": "Fundos", "treasure-titles": "Títulos do Tesouro",
    "customers": "Dados Cadastrais", "exchanges": "Câmbio",
}

LABEL_MAP = {
    "ITAÚ UNIBANCO": "Itaú Unibanco", "CAIXA ECONOMICA FEDERAL": "Caixa Econômica Federal",
    "BANCO DO BRASIL": "Banco do Brasil", "MERCADO PAGO": "Mercado Pago",
    "SANTANDER BRASIL": "Santander Brasil", "BRADESCO": "Bradesco", "NUBANK": "Nubank",
}

AVATAR_MAP = {"BRADESCO":"BDC","NUBANK":"NU","ITAÚ UNIBANCO":"ITÁ","BANCO DO BRASIL":"BB","CAIXA ECONOMICA FEDERAL":"CEF","MERCADO PAGO":"MP","SANTANDER BRASIL":"SAN"}
AVATAR_COLORS = {"BRADESCO":"#C8102E","NUBANK":"#820AD1","ITAÚ UNIBANCO":"#EC7000","BANCO DO BRASIL":"#FBBA00","CAIXA ECONOMICA FEDERAL":"#005CA9","MERCADO PAGO":"#009EE3","SANTANDER BRASIL":"#EC0000"}

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
    if n >= 1_000: return f"{n/1_000:.1f} Mi".replace(".", ",")
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

def classify_archetype(c: dict):
    if c.get("Crédito", 0) > 0.45: return "FOCO EM CRÉDITO", "Consumo dominado por APIs de crédito."
    if c.get("Investimentos", 0) > 0.40: return "FOCO EM INVESTIMENTOS", "Consumo concentrado em renda fixa, variável e fundos."
    if c.get("Conta", 0) > 0.50: return "FOCO EM CONTA CORRENTE", "Consumo predominante de dados de conta."
    if c.get("Crédito", 0) > 0.30 and c.get("Conta", 0) > 0.25: return "CRÉDITO & CONTA", "Mix equilibrado."
    if c.get("Investimentos", 0) > 0.25 and c.get("Crédito", 0) > 0.25: return "CRÉDITO & INVEST", "Combinação relevante."
    if c.get("Identidade", 0) > 0.30: return "FOCO EM IDENTIDADE", "Alta proporção cadastral."
    return "PERFIL DIVERSIFICADO", "Consumo distribuído."

def get_receptor_profile(institution: str, from_date: str = "2000-01-01", to_date: str = "2100-01-01"):
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # HEADER KPIS - START
    # 1. Total Reqs
    cur.execute("SELECT SUM(total) AS total_req, MIN(date) AS first_date, MAX(date) AS last_date FROM api_requests WHERE receptor_uuid = ? AND status = 200", (institution,))
    kpi1 = cur.fetchone()
    # 2. Consents
    cur.execute("SELECT total AS current_consents, date AS current_date FROM unique_consents WHERE receptor_uuid = ? ORDER BY date DESC LIMIT 1", (institution,))
    kpi2_curr = cur.fetchone()
    cur.execute("SELECT total AS first_consents FROM unique_consents WHERE receptor_uuid = ? ORDER BY date ASC LIMIT 1", (institution,))
    kpi2_first = cur.fetchone()
    
    # Global Rankings
    cur.execute("SELECT receptor_uuid, SUM(CASE WHEN status = 500 THEN total ELSE 0 END)*1.0/SUM(total) AS err_rate, COUNT(DISTINCT transmitter_uuid) AS n_transmitters, SUM(CASE WHEN status = 200 THEN total ELSE 0 END) AS vol_req FROM api_requests GROUP BY receptor_uuid")
    all_ranks = cur.fetchall()
    
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
    tx_rank = get_rank(tx_sorted, "n_transmitters")
    vol_rank = get_rank(vol_sorted, "vol_req")
    
    my_err_rate = next((x["err_rate"] for x in all_ranks if x["receptor_uuid"] == institution), 0) or 0
    my_tx = next((x["n_transmitters"] for x in all_ranks if x["receptor_uuid"] == institution), 0) or 0
    
    ordinals_pt = {1:"1º", 2:"2º", 3:"3º", 4:"4º", 5:"5º", 6:"6º", 7:"7º"}
    ext_ord = lambda r: ordinals_pt.get(r, f"{r}º")
    
    # 3. Intensity 30D
    cur.execute("SELECT MAX(r.date) AS ref_date FROM api_requests r JOIN unique_consents c ON r.date=c.date AND r.receptor_uuid=c.receptor_uuid WHERE r.receptor_uuid=? AND r.status=200 AND r.api NOT IN ('consents','resources')", (institution,))
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

    # Name mapping
    cur.execute("SELECT receptor FROM unique_consents WHERE receptor_uuid = ? LIMIT 1", (institution,))
    rname = cur.fetchone()
    inst_name = rname["receptor"] if rname else institution
    inst_clean_name = LABEL_MAP.get(inst_name, inst_name.title())

    # Build Header KPIs
    header = {
        "avatar": {
            "initials": AVATAR_MAP.get(inst_name, "".join(w[0] for w in inst_clean_name.split())[:3].upper()),
            "background_color": AVATAR_COLORS.get(inst_name, avatar_color_fallback(institution)),
            "text_color": "#1A1A2E" if AVATAR_COLORS.get(inst_name) == "#FBBA00" else "#FFFFFF"
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
        "subtitle": "Req / consent / 30d (atual)",
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
    # END HEADER

    # REST OF EXISTING LOGIC
    cur.execute("""SELECT api, SUM(total) AS total FROM api_requests WHERE receptor_uuid = :receptor AND api NOT IN ('consents','resources') AND status = 200 AND date >= :from_date AND date <= :to_date GROUP BY api""", {"receptor": institution, "from_date": from_date, "to_date": to_date})
    inst_totals = {r["api"]: r["total"] for r in cur.fetchall()}

    cur.execute("""SELECT api, SUM(total) AS total FROM api_requests WHERE api NOT IN ('consents','resources') AND status = 200 AND date >= :from_date AND date <= :to_date GROUP BY api""", {"from_date": from_date, "to_date": to_date})
    eco_totals = {r["api"]: r["total"] for r in cur.fetchall()}

    if sum(inst_totals.values()) == 0:
        con.close()
        return None
    
    category_shares = {}
    inst_total_all = sum(inst_totals.values())
    eco_total_all = sum(eco_totals.values())
    for group_name, group_info in API_GROUPS.items():
        g_inst = sum(inst_totals.get(a, 0) for a in group_info["apis"])
        category_shares[group_name] = g_inst / inst_total_all if inst_total_all > 0 else 0

    # Tornado: fluxo bilateral de transmissores (institution = receptor_uuid)
    tornado_data = _get_tornado_data(cur, institution, inst_clean_name)
        
    archetype_name, archetype_desc = classify_archetype(category_shares)
    header["archetype"] = archetype_name

    cur.execute("""SELECT r.date, r.api, r.endpoint, SUM(r.total) AS req_week, MAX(c.cpf) AS consents_cpf, MAX(c.cnpj) AS consents_cnpj, MAX(c.total) AS consents_total FROM api_requests r JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid WHERE r.receptor_uuid = :receptor AND r.api NOT IN ('consents', 'resources') AND r.status = 200 AND r.date >= :from_date AND r.date <= :to_date GROUP BY r.date, r.api, r.endpoint ORDER BY r.date, r.api, r.endpoint""", {"receptor": institution, "from_date": from_date, "to_date": to_date})
    intensities = cur.fetchall()

    mix_dict = defaultdict(lambda: defaultdict(float))
    endpoint_series = defaultdict(list)
    weeks_set = set()
    latest_date = max_consents = 0; active_apis = set()

    for r in intensities:
        dt = r["date"]
        weeks_set.add(dt)
        if not latest_date or dt > latest_date:
            latest_date = dt; max_consents = max(max_consents, r["consents_total"])
        consents = _get_consents(r)
        week_val  = normalize(r["req_week"], consents, 7)   # req/consent/semana → mix_data
        month_val = normalize(r["req_week"], consents, 30)  # req/consent/30d    → endpoint_data
        mix_dict[dt][r["api"].replace("-", "_")] += week_val
        active_apis.add(r["api"])
        endpoint_series[(r["api"], r["endpoint"])].append(month_val)


    con.close()
    mix_data = [{"date": dt[:10], **{a.replace("-", "_"): 0.0 for gs in API_GROUPS.values() for a in gs["apis"]}, **mix_dict[dt]} for dt in sorted(mix_dict.keys())]
    endpoint_data = {}
    for gn, gi in API_GROUPS.items():
        g_str = {"color": gi["color"], "apis": {}}
        for api in gi["apis"]:
            api_eps = {ep: sum(vs)/len(vs) for (ap, ep), vs in endpoint_series.items() if ap == api and vs}
            if api_eps: g_str["apis"][api] = {"label": API_LABELS.get(api, api), "endpoints": api_eps}
        if g_str["apis"]: endpoint_data[gn] = g_str

    # Mapa Estratégico: calculado com a conn já aberta
    strategic_map = _get_strategic_map(from_date, to_date)

    return {
        "institution": {"id": institution, "label": inst_clean_name, "uuid": institution, "archetype": archetype_name, "archetype_description": archetype_desc},
        "header": header, "summary": {"total_consents": max_consents, "active_apis": len(active_apis), "weeks_count": len(weeks_set)},
        "mix_data": mix_data, "tornado_data": tornado_data, "endpoint_data": endpoint_data,
        "strategic_map": strategic_map,
        "period": {"from": min(weeks_set) if weeks_set else from_date, "to": max(weeks_set) if weeks_set else to_date, "weeks_count": len(weeks_set)}
    }


@functools.lru_cache(maxsize=4)
def _get_strategic_map(from_date: str, to_date: str) -> dict:
    """Calcula o Mapa Estratégico: intensidade por grupo para todos os receptores.
    Usa receptor_uuid no JOIN (chave indexada) para performance.
    """
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1. Últimas 4 semanas com dados (join por receptor_uuid — chave rápida)
    cur.execute("""
        SELECT DISTINCT r.date
        FROM api_requests r
        JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
        WHERE r.status = 200
          AND r.date >= ? AND r.date <= ?
        ORDER BY r.date DESC LIMIT 4
    """, (from_date, to_date))
    weeks = [r["date"] for r in cur.fetchall()]
    if not weeks:
        con.close()
        return {"reference_weeks": [], "all_receptors": {}, "group_stats": {}}

    ph = ",".join("?" * len(weeks))

    # 2. Intensidade semanal por receptor_uuid e grupo (query consolidada)
    cur.execute(f"""
        SELECT r.receptor_uuid, r.receptor,
               CASE
                   WHEN r.api = 'accounts'                                               THEN 'Conta'
                   WHEN r.api = 'credit-cards-accounts'                                  THEN 'Cartao'
                   WHEN r.api IN ('bank-fixed-incomes','credit-fixed-incomes',
                                  'variable-incomes','funds','treasure-titles')           THEN 'Investimento'
                   WHEN r.api IN ('loans','financings','invoice-financings',
                                  'unarranged-accounts-overdraft')                        THEN 'Credito'
                   WHEN r.api = 'exchanges'                                              THEN 'Cambio'
                   WHEN r.api = 'customers'                                              THEN 'Identidade'
                   WHEN r.api = 'resources'                                              THEN 'Resource'
               END AS grp,
               r.date,
               SUM(r.total) AS req_week,
               c.total      AS consents_total
        FROM api_requests r
        JOIN unique_consents c ON r.date = c.date AND r.receptor_uuid = c.receptor_uuid
        WHERE r.api NOT IN ('consents')
          AND r.status = 200
          AND r.date IN ({ph})
        GROUP BY r.receptor_uuid, r.date, grp
        HAVING grp IS NOT NULL
    """, weeks)
    rows = cur.fetchall()
    con.close()

    # 3. Agrupar por (receptor_uuid, grupo) → lista de intensidades semanais
    weekly = defaultdict(lambda: defaultdict(list))
    receptor_labels = {}
    for row in rows:
        cons = float(row["consents_total"] or 0)
        if cons <= 0:
            continue
        intensity = (row["req_week"] / cons) * (30.0 / 7)
        uid = row["receptor_uuid"]
        weekly[uid][row["grp"]].append(intensity)
        if uid not in receptor_labels:
            receptor_labels[uid] = LABEL_MAP.get(row["receptor"], row["receptor"].title())

    # 4. Média das 4 semanas por (receptor, grupo)
    GROUPS = ["Conta", "Cartao", "Investimento", "Credito", "Cambio", "Identidade", "Resource"]
    all_receptors = {}  # keyed by display label
    for uid, groups in weekly.items():
        label = receptor_labels.get(uid, uid)
        all_receptors[label] = {
            grp: round(sum(vals) / len(vals), 2)
            for grp, vals in groups.items()
        }

    # 5. GROUP_STATS: mean, median, Q3 (upper_half = vals[n - n//2:])
    group_stats = {}
    for grp in GROUPS:
        vals = sorted(all_receptors[rec].get(grp, 0.0) for rec in all_receptors)
        n = len(vals)
        if n == 0:
            group_stats[grp] = {"mean": 0, "median": 0, "q3": 0}
            continue
        mean_v   = sum(vals) / n
        median_v = statistics.median(vals)
        upper    = vals[n - n // 2:]
        q3_v     = statistics.median(upper)
        group_stats[grp] = {
            "mean":   round(mean_v,   2),
            "median": round(median_v, 2),
            "q3":     round(q3_v,     2),
        }

    return {
        "reference_weeks": weeks,
        "all_receptors":   all_receptors,
        "group_stats":     group_stats,
    }



def _get_tornado_data(cur, institution_uuid: str, inst_display_name: str) -> dict:
    """Calcula o fluxo bilateral de requisições entre a instituição (por UUID) e cada par."""
    # 1. Últimas 4 semanas com dados
    cur.execute("SELECT DISTINCT date FROM api_requests WHERE status=200 ORDER BY date DESC LIMIT 4")
    weeks = [r["date"] for r in cur.fetchall()]
    if not weeks:
        return {"reference_weeks": [], "scale_max": 0, "left_label": "", "right_label": "", "rows": []}

    placeholders = ",".join("?" * len(weeks))

    # 2. LEFT: institution_uuid como receptor — ela consulta transmissores
    cur.execute(f"""
        SELECT transmitter AS institution_name, transmitter_uuid AS institution_uuid,
               SUM(total) * 30.0 / 28.0 / 1e6 AS value_30d
        FROM api_requests
        WHERE receptor_uuid = ?
          AND status = 200
          AND api NOT IN ('consents', 'resources')
          AND date IN ({placeholders})
        GROUP BY transmitter, transmitter_uuid
    """, [institution_uuid] + weeks)
    left_rows = [dict(r) for r in cur.fetchall()]

    # 3. RIGHT: institution_uuid como transmissor — outros a consultam
    cur.execute(f"""
        SELECT receptor AS institution_name, receptor_uuid AS institution_uuid,
               SUM(total) * 30.0 / 28.0 / 1e6 AS value_30d
        FROM api_requests
        WHERE transmitter_uuid = ?
          AND status = 200
          AND api NOT IN ('consents', 'resources')
          AND date IN ({placeholders})
        GROUP BY receptor, receptor_uuid
    """, [institution_uuid] + weeks)
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

