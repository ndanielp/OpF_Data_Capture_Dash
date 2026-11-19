"""
export.py — API de exportação de dados (feature 015). Contrato: specs/015-export-portal/contracts/export-api.md

Somente leitura. Todas as rotas exigem o código de acesso (token de sessão), exceto o download,
que usa um ticket de 60 s assinado. Nenhuma rota recebe nome de tabela livre: só ids de
`EXPORT_TABLES`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.background import BackgroundTask

from services import export as X

router = APIRouter()


def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def require_session(request: Request) -> None:
    if X.verify_token("session", request.headers.get("X-Export-Token")) is None:
        raise HTTPException(401, detail=X.MSG_SESSION)


def _client_ip(request: Request) -> str:
    # Cloud Run acrescenta o IP do cliente ao fim de X-Forwarded-For; entradas à esquerda podem ser forjadas.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


class _Login(BaseModel):
    code: str = Field(min_length=1, max_length=128)


@router.post("/session")
def create_session(body: _Login, request: Request):
    ip = _client_ip(request)
    if X.limiter.blocked(ip):
        return _no_store(JSONResponse({"detail": X.MSG_BLOCKED, "retry_after": X.BLOCK_S}, status_code=429,
                                      headers={"Retry-After": str(X.BLOCK_S)}))
    if not X.code_matches(body.code):
        X.limiter.fail(ip)
        if X.limiter.blocked(ip):
            return _no_store(JSONResponse({"detail": X.MSG_BLOCKED, "retry_after": X.BLOCK_S}, status_code=429,
                                          headers={"Retry-After": str(X.BLOCK_S)}))
        return _no_store(JSONResponse({"detail": X.MSG_BAD_CODE}, status_code=401))
    X.limiter.ok(ip)
    token, exp = X.make_session()
    return _no_store(JSONResponse({"token": token,
                                   "expires_at": datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}))


@router.get("/options", dependencies=[Depends(require_session)])
def options():
    return _no_store(JSONResponse(X.options()))


def _422(e: ValidationError) -> HTTPException:
    msgs = [str(err.get("msg", "")).removeprefix("Value error, ") for err in e.errors()]
    return HTTPException(422, detail="; ".join(m for m in msgs if m) or "Filtros inválidos.")


@router.get("/count", dependencies=[Depends(require_session)])
def count(
    tables: str = Query(...), start: Optional[str] = Query(None), end: Optional[str] = Query(None),
    receptors: Optional[str] = Query(None), transmitters: Optional[str] = Query(None),
    apis: Optional[str] = Query(None), status: str = Query("all"), level: str = Query("api"),
):
    try:
        req = X.request_from_query(tables, start, end, receptors, transmitters, apis, status, level)
    except ValidationError as e:
        raise _422(e)
    return _no_store(JSONResponse(X.count_rows(req)))


@router.post("/ticket", dependencies=[Depends(require_session)])
def ticket(req: X.ExportRequest):
    return _no_store(JSONResponse({"url": "/api/v2/export/file?ticket=" + X.make_ticket(req),
                                   "filename": X.file_name(req), "expires_in": X.TICKET_TTL_S}))


def _guarded(gen: Iterator[bytes], lease: X.SlotLease) -> Iterator[bytes]:
    try:
        yield from gen
    finally:
        lease.release()


@router.get("/file")
def file(ticket: str = Query("")):
    req = X.request_from_ticket(ticket)
    if req is None:
        raise HTTPException(401, detail=X.MSG_TICKET)
    lease = X.slots.acquire()
    if lease is None:
        raise HTTPException(429, detail=X.MSG_BUSY)
    try:
        multi = len(req.tables) > 1
        gen = X.iter_zip(req) if multi else X.iter_csv(req.tables[0], req)
        headers = {
            "Content-Disposition": f'attachment; filename="{X.file_name(req)}"',
            "Access-Control-Expose-Headers": "X-Rows-Total, X-Bytes-Estimate, Content-Disposition",
            "Cache-Control": "no-store",
        }
        # Só usa a contagem que a aba já pediu (em cache): contar aqui atrasaria o primeiro byte.
        count = X.cached_count(req)
        if count:
            headers["X-Rows-Total"] = str(count["total_rows"])
            headers["X-Bytes-Estimate"] = str(count["total_bytes_estimate"])
        # O lease é solto ao fim do gerador (fim normal ou desconexão) e pela tarefa de fundo, caso o
        # gerador nem tenha iniciado; release é idempotente.
        return StreamingResponse(_guarded(gen, lease), media_type="application/zip" if multi else "text/csv; charset=utf-8",
                                 headers=headers, background=BackgroundTask(lease.release))
    except BaseException:
        lease.release()
        raise
