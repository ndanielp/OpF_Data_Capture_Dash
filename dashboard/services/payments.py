"""
payments.py — Tema Pagamentos do Dashboard 2.0 (feature 018).

Lê só `payment_weekly` (pré-agregação do coletor). Regras: specs/018-pagamentos-dash/research.md.
- Transação = 200 em Criar iniciação (65 em `payments`, 129 em `automatic-payments`); falha = 500 ÷ (200 + 500).
- Iniciadora = receptor; detentora = transmissor.
- Janela = 4 semanas até a semana W; por 30 dias = soma × 30/28.
- Mês = soma ÷ semanas daquele mês na base × 30/7 (meses de 4 e 5 semanas comparáveis).
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from cachetools import TTLCache

from services import v2_metrics as M
from services.constants import PAYMENT_APIS, PAYMENT_HEAT, resolve_institution_group

TableMissing = M.TableMissing

APIS: tuple[str, ...] = tuple(PAYMENT_APIS)
_CREATE = {meta["endpoint"]: api for api, meta in PAYMENT_APIS.items()}
_POLL = {api: meta["poll_endpoint"] for api, meta in PAYMENT_APIS.items()}
ENROLL_STEPS: tuple[tuple[int, str], ...] = (
    (133, "Vínculo iniciado"), (139, "Sinais de risco enviados"),
    (136, "Autorizado no detentor"), (137, "Vínculo ativo"),
)
ENROLL_ENDED = 135
ROLES = ("ini", "det")
_KEY = {"ini": "r", "det": "t"}          # coluna da instituição em cada papel
_OTHER = {"ini": "t", "det": "r"}        # coluna da contraparte
_OTHER_LABEL = {"ini": "Outras detentoras", "det": "Outras iniciadoras"}

WINDOW_DAYS = 28
TOP_N = 8
MAX_MONTHS = 12
TX_FLOOR = 30_000          # transações (ou tentativas) por 30 dias
ENROLL_FLOOR = 1_000       # vínculos iniciados por 30 dias
VOLUME_DOWN, VOLUME_UP = -0.10, 0.20
RATE_PP = 0.05

_memo: TTLCache = TTLCache(maxsize=32, ttl=24 * 3600)


def _cached(name: str, fn: Callable[[], Any]) -> Any:
    """Resultado derivado da base, guardado enquanto a base não muda (chave com o mtime)."""
    key = (M._db_key(), name)
    if key not in _memo:
        _memo[key] = fn()
    return _memo[key]


# ── Base ──────────────────────────────────────────────────────────────────────

def _load() -> dict:
    raw = M._query(
        "SELECT date, receptor_uuid AS r, receptor AS rn, transmitter_uuid AS t, transmitter AS tn, "
        "endpoint_id AS ep, status, total FROM payment_weekly")
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["total"] = df["total"].astype(float)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    weeks = sorted(df["date"].unique())
    weeks_in_month = pd.Series(pd.to_datetime(weeks)).dt.strftime("%Y-%m").value_counts()
    latest = df.sort_values("date")
    names = {**latest.drop_duplicates("t", keep="last").set_index("t")["tn"].to_dict(),
             **latest.drop_duplicates("r", keep="last").set_index("r")["rn"].to_dict()}

    tx = df[df["ep"].isin(_CREATE)]
    tx = tx.assign(api=tx["ep"].map(_CREATE)).pivot_table(
        index=["date", "month", "r", "t", "api"], columns="status", values="total", aggfunc="sum", fill_value=0.0)
    tx = tx.reindex(columns=[200, 500], fill_value=0.0).rename(columns={200: "ok", 500: "fail"}).reset_index()
    tx.columns.name = None

    months = sorted(weeks_in_month.index)[-MAX_MONTHS:]
    return {
        "df": df, "tx": tx, "names": names,
        "weeks": [pd.Timestamp(w) for w in weeks],
        "week": pd.Timestamp(weeks[-1]) if weeks else None,
        "months": months,
        "factor": {m: 30 / 7 / weeks_in_month[m] for m in weeks_in_month.index},
    }


def base() -> dict:
    """Tabela carregada uma vez por versão da base. Levanta TableMissing sem payment_weekly."""
    return _cached("base", _load)


def short(uuid: str) -> str:
    return M.short_name(base()["names"].get(uuid, uuid))


def _in_window(dates: pd.Series, end: pd.Timestamp) -> pd.Series:
    return (dates > end - pd.Timedelta(days=WINDOW_DAYS)) & (dates <= end)


def _per30(v: float) -> float:
    return float(v) * 30 / WINDOW_DAYS


def _rate(fail: float, ok: float) -> float | None:
    return float(fail) / float(ok + fail) if ok + fail > 0 else None


def _window(end: pd.Timestamp) -> dict:
    return {"start": (end - pd.Timedelta(days=WINDOW_DAYS - 7)).strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


# ── /meta ─────────────────────────────────────────────────────────────────────

def _data_uuids() -> set[str]:
    try:
        return set(M.institutions()["uuid"])
    except TableMissing:
        return set()


def meta() -> dict:
    b = base()
    tx = b["tx"][b["tx"]["ok"] > 0]
    roles = {}
    for role in ROLES:
        for u in tx[_KEY[role]].unique():
            roles.setdefault(u, []).append(role)
    in_data = _data_uuids()
    months = b["months"]
    mtx = b["tx"][b["tx"]["month"].isin(months)]
    vol = {role: mtx.groupby([_KEY[role], "month"])["ok"].sum() for role in ROLES}

    def volume(u: str, role: str) -> list[float]:
        """Transações por 30 dias em cada mês, para a busca ordenar pelo mês escolhido."""
        return [round(float(vol[role].get((u, m), 0.0)) * b["factor"][m], 1) for m in months]

    insts = sorted(({"uuid": u, "name": b["names"].get(u, u), "short": short(u),
                     "group": resolve_institution_group(b["names"].get(u, "")), "roles": rs, "in_data": u in in_data,
                     "volume": {role: volume(u, role) for role in ROLES}}
                    for u, rs in roles.items()), key=lambda i: i["short"].lower())
    return {
        "data_through": b["week"].strftime("%Y-%m-%d") if b["week"] is not None else None,
        "months": b["months"],
        "apis": [{"slug": k, **{f: v[f] for f in ("label", "short", "endpoint", "color", "line", "color_dark", "line_dark")}}
                 for k, v in PAYMENT_APIS.items()],
        "heat": PAYMENT_HEAT,
        "institutions": insts,
    }


# ── /ranking ──────────────────────────────────────────────────────────────────

def _by_api(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """Índice = instituição; colunas (ok|fail, api), em contagem da janela."""
    t = frame.pivot_table(index=key, columns="api", values=["ok", "fail"], aggfunc="sum", fill_value=0.0)
    cols = pd.MultiIndex.from_product([["ok", "fail"], list(APIS)])
    return t.reindex(columns=cols, fill_value=0.0)


def _period(month: str | None) -> tuple[pd.DataFrame, pd.DataFrame, float, float, dict]:
    """Recorte atual e anterior do ranking, com o fator para 30 dias de cada um.
    Sem mês: últimas 4 semanas contra as 4 anteriores. Com mês: o mês contra o anterior."""
    b = base()
    tx, week = b["tx"], b["week"]
    if month is None:
        cur = tx[_in_window(tx["date"], week)]
        prev = tx[_in_window(tx["date"], week - pd.Timedelta(days=WINDOW_DAYS))]
        k = 30 / WINDOW_DAYS
        return cur, prev, k, k, {"kind": "window", "window": _window(week)}
    i = b["months"].index(month)
    prev_m = b["months"][i - 1] if i > 0 else None
    cur = tx[tx["month"] == month]
    prev = tx[tx["month"] == prev_m] if prev_m else tx.iloc[0:0]
    last_day = (pd.Timestamp(month + "-01") + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
    return cur, prev, b["factor"][month], b["factor"].get(prev_m, 0.0), {
        "kind": "month", "month": month, "prev_month": prev_m,
        "window": {"start": month + "-01", "end": last_day}}


def ranking(role: str, api: str, limit: int, pinned: list[str], excluded: list[str],
            month: str | None = None) -> dict:
    """ValueError quando `month` não está entre os meses da base."""
    b = base()
    week, key = b["week"], _KEY[role]
    if month is not None and month not in b["months"]:
        raise ValueError(month)
    cur, prev, k, kp, period = _period(month)
    apis = list(APIS) if api == "all" else [api]

    tot_ok = {a: float(cur.loc[cur["api"] == a, "ok"].sum()) * k for a in APIS}
    tot_fail = {a: float(cur.loc[cur["api"] == a, "fail"].sum()) * k for a in APIS}
    total = sum(tot_ok.values())
    prev_ok = {a: float(prev.loc[prev["api"] == a, "ok"].sum()) * kp for a in APIS}
    prev_total = sum(prev_ok.values())
    eco = {
        "total": total,
        "initiators": int(cur.loc[cur["ok"] > 0, "r"].nunique()),
        "holders": int(cur.loc[cur["ok"] > 0, "t"].nunique()),
        "ip_share_prev": prev_ok["payments"] / prev_total if prev_total else None,
    }
    for a in APIS:
        eco[a] = {"value": tot_ok[a], "share": tot_ok[a] / total if total else None,
                  "fail": _rate(tot_fail[a], tot_ok[a])}

    c, p = _by_api(cur, key) * k, _by_api(prev, key) * kp
    value = c["ok"][apis].sum(axis=1)
    prev_value = p["ok"][apis].sum(axis=1).reindex(value.index, fill_value=0.0)
    api_total = sum(tot_ok[a] for a in apis)

    def row(u: str) -> dict:
        v, pv = float(value.get(u, 0.0)), float(prev_value.get(u, 0.0))
        return {
            "uuid": u, "name": short(u), "group": resolve_institution_group(b["names"].get(u, "")),
            "pinned": u in pinned, "cut": False,
            **{a: float(c.at[u, ("ok", a)]) if u in c.index else 0.0 for a in APIS},
            "value": v, "share": v / api_total if api_total else None,
            "fail": {a: _rate(c.at[u, ("fail", a)], c.at[u, ("ok", a)]) if u in c.index else None for a in APIS},
            "growth": v / pv - 1 if pv > 0 else None,
        }

    ranked = [u for u in value[value > 0].sort_values(ascending=False).index if u not in excluded]
    rows = [row(u) for u in ranked[:limit]]
    extra = [row(u) for u in ranked[limit:] if u in pinned]
    if extra:
        extra[0]["cut"] = True
    return {
        "week": week.strftime("%Y-%m-%d"), "window": period.pop("window"), "period": period,
        "role": role, "api": api, "ecosystem": eco, "rows": rows + extra,
        "excluded": [{"uuid": u, "name": short(u)} for u in excluded if u in b["names"]],
    }


# ── /flows ────────────────────────────────────────────────────────────────────

def _top(frame: pd.DataFrame, col: str, n: int) -> list[str]:
    s = frame.groupby(col)["ok"].sum()
    return list(s[s > 0].sort_values(ascending=False).index[:n])


def _monthly_cells(frame: pd.DataFrame, b: dict, rows: list, cols: list,
                   row_of: Callable[[str], int], col_of: Callable[[str], int]) -> dict:
    """{api: {mês: {ok: [[...]], fail: [[...]]}}} por 30 dias; linhas e colunas pelo índice dado."""
    f = frame[frame["month"].isin(b["months"])]
    f = f.assign(i=f["r"].map(row_of), j=f["t"].map(col_of))
    g = f.groupby(["api", "month", "i", "j"])[["ok", "fail"]].sum()
    out: dict = {}
    for a in APIS:
        out[a] = {}
        for m in b["months"]:
            k = b["factor"][m]
            ok = [[0.0] * len(cols) for _ in rows]
            fail = [[0.0] * len(cols) for _ in rows]
            if (a, m) in g.index.droplevel([2, 3]):
                for (i, j), r in g.loc[(a, m)].iterrows():
                    ok[i][j] = round(float(r["ok"]) * k, 1)
                    fail[i][j] = round(float(r["fail"]) * k, 1)
            out[a][m] = {"ok": ok, "fail": fail}
    return out


MAX_PICK = 12


def _others(n: int, label: str) -> dict:
    return {"uuid": None, "name": label, "others_count": n}


def flows(size: int, rows: list[str] | None = None, cols: list[str] | None = None) -> dict:
    """Linhas e colunas: as escolhidas (na ordem dada) ou as `size` maiores; o resto vai para "Outras"."""
    b = base()
    tx, week = b["tx"], b["week"]
    cur = tx[_in_window(tx["date"], week)]
    known = b["names"]
    pick_r = [u for u in dict.fromkeys(rows or []) if u in known] or _top(cur, "r", size)
    pick_t = [u for u in dict.fromkeys(cols or []) if u in known] or _top(cur, "t", size)
    n_r = int(tx.loc[tx["ok"] > 0, "r"].nunique()) - len(set(pick_r) & set(tx.loc[tx["ok"] > 0, "r"]))
    n_t = int(tx.loc[tx["ok"] > 0, "t"].nunique()) - len(set(pick_t) & set(tx.loc[tx["ok"] > 0, "t"]))
    out_r = [{"uuid": u, "name": short(u)} for u in pick_r] + [_others(n_r, "Outras iniciadoras")]
    out_c = [{"uuid": u, "name": short(u)} for u in pick_t] + [_others(n_t, "Outras detentoras")]
    ri, ci = {u: i for i, u in enumerate(pick_r)}, {u: j for j, u in enumerate(pick_t)}
    data = _monthly_cells(tx, b, out_r, out_c, lambda u: ri.get(u, len(pick_r)), lambda u: ci.get(u, len(pick_t)))
    return {"months": b["months"], "week": week.strftime("%Y-%m-%d"), "rows": out_r, "cols": out_c, "data": data}


# ── /enrollment ───────────────────────────────────────────────────────────────

def enrollment(receptor: str | None = None, transmitter: str | None = None) -> dict:
    b = base()
    df, week = b["df"], b["week"]
    en = df[(df["status"] == 200) & df["ep"].isin([e for e, _ in ENROLL_STEPS] + [ENROLL_ENDED])]
    if receptor:
        en = en[en["r"] == receptor]
    if transmitter:
        en = en[en["t"] == transmitter]
    cur = en[_in_window(en["date"], week)].groupby("ep")["total"].sum()
    v = {e: _per30(cur.get(e, 0.0)) for e, _ in ENROLL_STEPS}
    monthly = en[en["month"].isin(b["months"])].groupby(["month", "ep"])["total"].sum()

    def conv(m: str) -> float | None:
        start = float(monthly.get((m, 133), 0.0))
        return float(monthly.get((m, 137), 0.0)) / start if start else None

    return {
        "window": _window(week),
        "steps": [{"endpoint": e, "label": label, "value": v[e]} for e, label in ENROLL_STEPS],
        "ended": _per30(cur.get(ENROLL_ENDED, 0.0)),
        "conversion": v[137] / v[133] if v[133] else None,
        "authorization": v[136] / v[139] if v[139] else None,
        "monthly": [{"month": m, "conversion": conv(m)} for m in b["months"]],
    }


# ── /changes ──────────────────────────────────────────────────────────────────

def _conditions(end: pd.Timestamp) -> dict[tuple, dict]:
    """Condições de mudança com a janela terminando em `end` (R5). Chave: (uuid, papel, tipo, api)."""
    b = base()
    tx, df = b["tx"], b["df"]
    prev_end = end - pd.Timedelta(days=WINDOW_DAYS)
    cur, prev = tx[_in_window(tx["date"], end)], tx[_in_window(tx["date"], prev_end)]
    en = df[(df["status"] == 200) & df["ep"].isin([133, 137])]
    en_cur, en_prev = en[_in_window(en["date"], end)], en[_in_window(en["date"], prev_end)]
    found: dict[tuple, dict] = {}

    def add(u: str, role: str, kind: str, api: str | None, before: float, after: float, change: float) -> None:
        found[(u, role, kind, api)] = {"uuid": u, "role": role, "kind": kind, "api": api,
                                       "direction": "up" if change > 0 else "down",
                                       "before": before, "after": after, "change": change}

    for role in ROLES:
        key = _KEY[role]
        c, p = _by_api(cur, key), _by_api(prev, key)
        for u in c.index.union(p.index):
            get = lambda t, col: float(t.at[u, col]) if u in t.index else 0.0   # noqa: E731
            vc = sum(get(c, ("ok", a)) for a in APIS)
            vp = sum(get(p, ("ok", a)) for a in APIS)
            if vp > 0 and max(_per30(vc), _per30(vp)) >= TX_FLOOR:
                ch = vc / vp - 1
                if ch <= VOLUME_DOWN or ch >= VOLUME_UP:
                    add(u, role, "volume", None, _per30(vp), _per30(vc), ch)
            for a in APIS:
                oc, fc, op, fp = get(c, ("ok", a)), get(c, ("fail", a)), get(p, ("ok", a)), get(p, ("fail", a))
                # Taxa só com base nas duas janelas: com poucas tentativas de um lado, ela salta à toa.
                if min(_per30(oc + fc), _per30(op + fp)) >= TX_FLOOR:
                    rc, rp = fc / (oc + fc), fp / (op + fp)
                    if abs(rc - rp) >= RATE_PP:
                        add(u, role, "fail", a, rp, rc, rc - rp)
        ec = en_cur.pivot_table(index=key, columns="ep", values="total", aggfunc="sum", fill_value=0.0)
        ep_ = en_prev.pivot_table(index=key, columns="ep", values="total", aggfunc="sum", fill_value=0.0)
        ec, ep_ = (t.reindex(columns=[133, 137], fill_value=0.0) for t in (ec, ep_))
        for u in ec.index.intersection(ep_.index):
            sc, sp = float(ec.at[u, 133]), float(ep_.at[u, 133])
            if min(_per30(sc), _per30(sp)) >= ENROLL_FLOOR:
                cc, cp = float(ec.at[u, 137]) / sc, float(ep_.at[u, 137]) / sp
                if abs(cc - cp) >= RATE_PP:
                    add(u, role, "conversion", None, cp, cc, cc - cp)
    return found


_KIND_ORDER = {"fail": 0, "volume": 1, "conversion": 2}


def _cond_at(w: pd.Timestamp) -> dict[tuple, dict]:
    return _cached("cond-" + w.strftime("%Y-%m-%d"), lambda: _conditions(w))


def _split(w: pd.Timestamp, prev: pd.Timestamp | None) -> tuple[list[dict], list[dict]]:
    """Confirmadas (condição em w e na semana anterior, mesma direção) e em observação (só em w)."""
    last, before = _cond_at(w), (_cond_at(prev) if prev is not None else {})
    same = lambda k, v: k in before and before[k]["direction"] == v["direction"]   # noqa: E731
    return [v for k, v in last.items() if same(k, v)], [v for k, v in last.items() if not same(k, v)]


def _month_week(m: str) -> tuple[pd.Timestamp, pd.Timestamp | None]:
    weeks = base()["weeks"]
    i = max(k for k, w in enumerate(weeks) if w.strftime("%Y-%m") == m)
    return weeks[i], (weeks[i - 1] if i > 0 else None)


def changes(month: str | None = None) -> dict:
    """Mudanças confirmadas no mês (W = última semana do mês). ValueError para mês fora da base."""
    b = base()
    months = b["months"]
    month = month or months[-1]
    if month not in months:
        raise ValueError(month)
    week, prev = _month_week(month)

    def out(items: list[dict]) -> list[dict]:
        items = [dict(i, name=short(i["uuid"])) for i in items]
        return sorted(items, key=lambda i: (_KIND_ORDER[i["kind"]], -abs(i["change"])))

    confirmed, watching = _split(week, prev)
    counts = _cached("changes-months", lambda: [{"month": m, "alerts": len(_split(*_month_week(m))[0])} for m in months])
    prev_end = week - pd.Timedelta(days=WINDOW_DAYS)
    return {
        "week": week.strftime("%Y-%m-%d"), "month": month, "months": counts,
        "window": {**_window(week), "prev_start": _window(prev_end)["start"], "prev_end": prev_end.strftime("%Y-%m-%d")},
        "floor": {"transactions": TX_FLOOR, "enrollments": ENROLL_FLOOR},
        "alerts": out(confirmed), "watching": out(watching) if month == months[-1] else [],
    }


# ── /institution ──────────────────────────────────────────────────────────────

def institution(uuid: str, role: str | None, counterparts: list[str] | None = None) -> dict:
    """KeyError quando o uuid não aparece em pagamentos."""
    b = base()
    tx, week = b["tx"], b["week"]
    if uuid not in b["names"]:
        raise KeyError(uuid)
    cur = tx[_in_window(tx["date"], week)]
    vol = {r: float(tx.loc[tx[_KEY[r]] == uuid, "ok"].sum()) for r in ROLES}
    roles = [r for r in ROLES if vol[r] > 0]
    if not roles:
        raise KeyError(uuid)
    if role not in roles:
        recent = {r: float(cur.loc[cur[_KEY[r]] == uuid, "ok"].sum()) for r in roles}
        role = max(roles, key=lambda r: (recent[r], vol[r]))
    key, other = _KEY[role], _OTHER[role]
    mine = tx[tx[key] == uuid]

    chosen = [u for u in dict.fromkeys(counterparts or []) if u in b["names"] and u != uuid]
    top = chosen or _top(mine[_in_window(mine["date"], week)], other, TOP_N) or _top(mine, other, TOP_N)
    rest = set(mine[other].unique()) - set(top)   # toda contraparte fora da lista cai em "Outras"
    cps = [{"uuid": u, "name": short(u)} for u in top] + ([_others(len(rest), _OTHER_LABEL[role])] if rest or chosen else [])
    idx = {u: i for i, u in enumerate(top)}
    pos = lambda u: idx.get(u, len(top))   # noqa: E731
    if role == "ini":
        cells = _monthly_cells(mine, b, [0], cps, lambda _u: 0, pos)
    else:
        cells = _monthly_cells(mine, b, cps, [0], pos, lambda _u: 0)
    data = {a: {m: {k: ([row[0] for row in v] if role == "det" else v[0]) for k, v in cells[a][m].items()}
                for m in b["months"]} for a in APIS}

    eco_m = tx[tx["month"].isin(b["months"])].groupby(["api", "month"])[["ok", "fail"]].sum()
    ecosystem = {a: {m: {k: round(float(eco_m.at[(a, m), k]) * b["factor"][m], 1) if (a, m) in eco_m.index else 0.0
                         for k in ("ok", "fail")} for m in b["months"]} for a in APIS}

    last_m = b["months"][-1]
    lm = tx[(tx["month"] == last_m)].groupby(key)["ok"].sum()
    lm = lm[lm > 0]
    me_last = float(lm.get(uuid, 0.0))
    rank = {"position": int((lm > me_last).sum()) + 1 if me_last > 0 else None, "of": int(len(lm))}

    df = b["df"]
    win = df[_in_window(df["date"], week) & (df[key] == uuid) & (df["status"] == 200)].groupby("ep")["total"].sum()
    polls = {a: (float(win.get(_POLL[a], 0.0)) / float(win[ep]) if float(win.get(ep, 0.0)) > 0 else None)
             for ep, a in _CREATE.items()}

    en = enrollment(receptor=uuid) if role == "ini" else enrollment(transmitter=uuid)
    eco_en = enrollment()
    return {
        "institution": {"uuid": uuid, "name": b["names"][uuid], "short": short(uuid),
                        "group": resolve_institution_group(b["names"][uuid]), "in_data": uuid in _data_uuids()},
        "role": role, "roles": roles, "months": b["months"], "week": week.strftime("%Y-%m-%d"),
        "counterparts": cps, "data": data, "ecosystem": ecosystem, "rank": rank, "polls": polls,
        "enrollment": en if en["steps"][0]["value"] > 0 else None,
        "enrollment_ecosystem": {"conversion": eco_en["conversion"], "authorization": eco_en["authorization"]},
    }


def warm() -> None:
    try:
        base()
        flows(TOP_N)
        changes()
        meta()
    except TableMissing:
        pass
