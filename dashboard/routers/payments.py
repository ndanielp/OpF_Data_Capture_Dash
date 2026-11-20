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
    limit:    int = Query(10, ge=1, le=50),
    pinned:   Optional[str] = Query(None),
    excluded: Optional[str] = Query(None),
) -> dict:
    role = _choice(role, P.ROLES, "role")
    api = _choice(api, _API_CHOICES, "api")
    return _or_unavailable(
        lambda: P.ranking(role, api, limit, _list(pinned), _list(excluded)),
        {"week": None, "window": None, "role": role, "api": api, "ecosystem": None, "rows": [], "excluded": []})


@router.get("/flows")
def flows(size: int = Query(P.TOP_N, ge=2, le=12)) -> dict:
    return _or_unavailable(lambda: P.flows(size), {"months": [], "week": None, "rows": [], "cols": [], "data": {}})


@router.get("/enrollment")
def enrollment(receptor: Optional[str] = Query(None), transmitter: Optional[str] = Query(None)) -> dict:
    if receptor and transmitter:
        raise HTTPException(422, detail="Use 'receptor' ou 'transmitter', não os dois.")
    return _or_unavailable(lambda: P.enrollment(receptor, transmitter),
                           {"window": None, "steps": [], "ended": None, "conversion": None,
                            "authorization": None, "monthly": []})


@router.get("/changes")
def changes() -> dict:
    return _or_unavailable(P.changes, {"week": None, "month": None, "window": None,
                                       "floor": {"transactions": P.TX_FLOOR, "enrollments": P.ENROLL_FLOOR},
                                       "alerts": [], "watching": []})


@router.get("/institution/{uuid}")
def institution(uuid: str, role: Optional[str] = Query(None)) -> dict:
    if role is not None:
        role = _choice(role, P.ROLES, "role")
    try:
        return _clean({**P.institution(uuid, role), "unavailable": []})
    except KeyError:
        raise HTTPException(404, detail="Instituição não encontrada nos dados de pagamento.")
    except P.TableMissing:
        return _clean({"institution": None, "role": role, "roles": [], "months": [], "week": None,
                       "counterparts": [], "data": {}, "ecosystem": {}, "rank": None, "polls": None,
                       "enrollment": None, "enrollment_ecosystem": None, "unavailable": ["payments"]})
