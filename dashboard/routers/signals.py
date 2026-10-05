"""
signals.py — FastAPI router para o card "O que mudou" (feature 010).

Endpoint:
  GET /api/signals — alertas de uma semana, agrupados por seção e instituição

Somente leitura: behavior_signals é escrita pelo data-loader (compute_signals.py).
Se a tabela ainda não existe na base, devolve a estrutura vazia — o dashboard não
cria nem altera tabelas (Constituição, Princípio V).
"""

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import config
from services.constants import INSTITUTION_GROUP_SLUGS
from services.of_analytics import resolve_institution_group

router = APIRouter()

SECTIONS: tuple[str, ...] = ("new_entrant", "increase", "decrease")


def _db_con() -> sqlite3.Connection:
    con = sqlite3.connect(str(config.DB_PATH))
    con.execute("PRAGMA busy_timeout = 3000")
    return con


def _parse_groups(groups_param: str | None) -> list[str] | None:
    """Mesma semântica dos endpoints da 009: slug desconhecido é ignorado."""
    if not groups_param:
        return None
    parts = [g.strip() for g in groups_param.split(",") if g.strip() in INSTITUTION_GROUP_SLUGS]
    return parts if parts else None


def _parse_week(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _empty() -> dict:
    return {
        "week": None,
        "weeks": [],
        "sections": {s: [] for s in SECTIONS},
        "api_incomplete": False,
        "computed_at": None,
        "consents_through": None,
        "api_through": None,
    }


@router.get("")
def list_signals(
    week:   Optional[str] = Query(None),
    groups: Optional[str] = Query(None),
) -> JSONResponse:
    """Alertas de uma semana (padrão: semana mais recente com dados), agrupados
    em seções e com uma entrada por instituição, ordenadas por volume."""
    grp = _parse_groups(groups)

    try:
        con = _db_con()
        try:
            rows = con.execute(
                "SELECT week, signal_type, metric, api_group, receptor_uuid, receptor, "
                "value_prev, value_curr, change_pct, volume FROM behavior_signals"
            ).fetchall()
            run = con.execute(
                "SELECT computed_at, consents_through, api_through, api_skipped_weeks "
                "FROM behavior_signals_run WHERE id = 1"
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        # Base anterior à primeira execução de compute_signals.py (tabela ausente).
        return JSONResponse(_empty())

    group_of = {name: resolve_institution_group(name) for name in {r[5] for r in rows}}
    if grp:
        rows = [r for r in rows if group_of[r[5]] in grp]

    counts = Counter(r[0] for r in rows)
    weeks = [{"week": w, "count": counts[w]} for w in sorted(counts, reverse=True)]

    computed_at, consents_through, api_through, skipped_json = run or (None, None, None, "[]")
    # Padrão = semana mais recente com dados coletados, mesmo que sem alertas:
    # o card mostra "nenhuma mudança relevante" em vez de pular para uma semana antiga.
    selected = _parse_week(week) or consents_through or (weeks[0]["week"] if weeks else None)

    entries: dict[tuple[str, str], dict] = {}
    for (wk, stype, metric, api_group, uuid, receptor,
         v_prev, v_curr, pct, volume) in rows:
        if wk != selected:
            continue
        key = (stype, uuid)
        entry = entries.setdefault(key, {
            "receptor": receptor,
            "institution_group": group_of[receptor],
            "volume": 0,
            "items": [],
        })
        entry["volume"] = max(entry["volume"], volume or 0)
        entry["items"].append({
            "metric": metric,
            "api_group": api_group or None,
            "value_prev": v_prev,
            "value_curr": v_curr,
            "change_pct": pct,
        })

    sections: dict[str, list] = defaultdict(list)
    for (stype, _uuid), entry in entries.items():
        entry["items"].sort(key=lambda i: (i["metric"], i["api_group"] or ""))
        sections[stype].append(entry)
    for stype in SECTIONS:
        sections[stype].sort(key=lambda e: (-e["volume"], e["receptor"]))

    try:
        skipped = set(json.loads(skipped_json or "[]"))
    except ValueError:
        skipped = set()

    return JSONResponse({
        "week": selected,
        "weeks": weeks,
        "sections": {s: sections[s] for s in SECTIONS},
        "api_incomplete": selected in skipped,
        "computed_at": computed_at,
        "consents_through": consents_through,
        "api_through": api_through,
    })
