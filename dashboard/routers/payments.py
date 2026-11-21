"""
payments.py — API do tema Pagamentos (feature 018). Contrato: specs/018-pagamentos-dash/contracts/payments-api.md

Somente leitura. Sem a tabela `payment_weekly` (coletor ainda não a gerou) cada rota responde 200
com `unavailable: ["payments"]`, nunca 500 (o painel não cria tabelas — Constituição, Princípio V).
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query

from routers.v2 import _choice, _clean, _list
from services import payments as P

router = APIRouter()

_API_CHOICES = ("all",) + P.APIS


def _month_guard(build: Callable[[], dict]) -> Callable[[], dict]:
    """Mês fora da base vira 422 (o serviço levanta ValueError)."""
    def run() -> dict:
        try:
            return build()
        except ValueError:
            raise HTTPException(422, detail="Mês inválido em 'month': use um dos meses de /meta.")
    return run


def _picks(s: Optional[str], field: str) -> list[str]:
    items = _list(s)
    if len(items) > P.MAX_PICK:
        raise HTTPException(422, detail=f"Escolha até {P.MAX_PICK} instituições em '{field}'.")
    return items


def _or_unavailable(build: Callable[[], dict], empty: dict) -> dict:
    try:
        return _clean({**build(), "unavailable": []})
    except P.TableMissing:
        return _clean({**empty, "unavailable": ["payments"]})


@router.get("/meta")
def meta() -> dict:
    return _or_unavailable(P.meta, {"data_through": None, "months": [], "apis": [], "heat": {}, "institutions": []})


@router.get("/ranking")
def ranking(
    role:     str = Query("ini"),
    api:      str = Query("all"),
    limit:    int = Query(10, ge=1, le=500),
    pinned:   Optional[str] = Query(None),
    excluded: Optional[str] = Query(None),
    month:    Optional[str] = Query(None),
) -> dict:
    role = _choice(role, P.ROLES, "role")
    api = _choice(api, _API_CHOICES, "api")
    return _or_unavailable(
        _month_guard(lambda: P.ranking(role, api, limit, _list(pinned), _list(excluded), month)),
        {"week": None, "window": None, "period": None, "role": role, "api": api, "ecosystem": None,
         "rows": [], "excluded": []})


@router.get("/flows")
def flows(size: int = Query(P.TOP_N, ge=2, le=12), rows: Optional[str] = Query(None),
          cols: Optional[str] = Query(None)) -> dict:
    r, c = _picks(rows, "rows"), _picks(cols, "cols")
    return _or_unavailable(lambda: P.flows(size, r, c), {"months": [], "week": None, "rows": [], "cols": [], "data": {}})


@router.get("/enrollment")
def enrollment(receptor: Optional[str] = Query(None), transmitter: Optional[str] = Query(None)) -> dict:
    if receptor and transmitter:
        raise HTTPException(422, detail="Use 'receptor' ou 'transmitter', não os dois.")
    return _or_unavailable(lambda: P.enrollment(receptor, transmitter),
                           {"window": None, "steps": [], "ended": None, "conversion": None,
                            "authorization": None, "monthly": []})


@router.get("/changes")
def changes(month: Optional[str] = Query(None)) -> dict:
    return _or_unavailable(_month_guard(lambda: P.changes(month)), {"week": None, "month": None, "months": [], "window": None,
                                       "floor": {"transactions": P.TX_FLOOR, "enrollments": P.ENROLL_FLOOR},
                                       "alerts": [], "watching": []})


@router.get("/institution/{uuid}")
def institution(uuid: str, role: Optional[str] = Query(None), counterparts: Optional[str] = Query(None)) -> dict:
    if role is not None:
        role = _choice(role, P.ROLES, "role")
    cps = _picks(counterparts, "counterparts")
    try:
        return _clean({**P.institution(uuid, role, cps), "unavailable": []})
    except KeyError:
        raise HTTPException(404, detail="Instituição não encontrada nos dados de pagamento.")
    except P.TableMissing:
        return _clean({"institution": None, "role": role, "roles": [], "months": [], "week": None,
                       "counterparts": [], "data": {}, "ecosystem": {}, "rank": None, "polls": None,
                       "enrollment": None, "enrollment_ecosystem": None, "unavailable": ["payments"]})
