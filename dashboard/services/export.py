"""
export.py — regras da exportação de dados (feature 015).

Somente leitura. A lista `EXPORT_TABLES` é a única fonte de nomes de tabela e de coluna que
chegam ao SQL: o usuário só escolhe ids dessa lista, e todo valor entra por placeholder `?`
(Constituição, Princípios V e II). Registros da coleta e análises derivadas não estão na lista
e, portanto, não têm caminho de saída.

Acesso: um código único e fixo (`EXPORT_CODE`, conferido só no servidor) vira uma chave HMAC; token de sessão (12 h) e ticket
de download (60 s) são assinados com ela. Sem estado no servidor, então valem entre instâncias do
Cloud Run e se invalidam sozinhos quando o código muda.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
import threading
import time
import zipfile
from datetime import date, datetime
from functools import lru_cache
from typing import Iterator, Literal, Optional

from cachetools import TTLCache
from pydantic import BaseModel, Field, field_validator, model_validator

import config

SERVER_SALT = b"opf-export-v1"
SESSION_TTL_S = 12 * 3600
TICKET_TTL_S = 60
LARGE_ROWS = 1_000_000
BATCH_ROWS = 5000
MAX_LIST_ITEMS = 200
MAX_PARALLEL_EXPORTS = 2

# Tentativas de código erradas: 5 em 10 min no mesmo IP bloqueiam por 60 s (FR-028).
ATTEMPT_WINDOW_S = 600
ATTEMPT_LIMIT = 5
BLOCK_S = 60

MSG_BAD_CODE = "Código inválido. Confira com quem administra o painel e tente de novo."
MSG_BLOCKED = "Muitas tentativas seguidas. Aguarde 1 minuto para tentar de novo."
MSG_SESSION = "O código de acesso mudou ou a sessão expirou. Digite o código para continuar."
MSG_TICKET = "Este link de download expirou. Volte à aba Exportar dados e exporte de novo."
MSG_BUSY = "Outra exportação grande está em andamento. Tente de novo em alguns minutos."

_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")   # UUIDs do portal; os valores só entram por placeholder
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


# ── Lista fechada de tabelas ──────────────────────────────────────────────────

def _cols(*items: tuple[str, str, str]) -> list[dict]:
    return [{"key": k, "label": label, "description": desc} for k, label, desc in items]


_C_DATE = ("date", "Semana", "Sexta-feira que fecha a semana (AAAA-MM-DD).")
_C_REC = ("receptor", "Receptor", "Nome da instituição receptora, como informado pelo portal.")
_C_REC_ID = ("receptor_uuid", "ID do receptor", "Identificador (UUID) da instituição receptora.")
_C_TX = ("transmitter", "Transmissor", "Nome da instituição transmissora (detentora de conta).")
_C_TX_ID = ("transmitter_uuid", "ID do transmissor", "Identificador (UUID) da instituição transmissora.")
_C_API = ("api", "API", "Identificador da API (ex.: accounts).")
_C_EP = ("endpoint", "Endpoint", "Nome do endpoint. Vazio no nível 'total por API'.")
_C_EP_ID = ("endpoint_id", "ID do endpoint", "Identificador do endpoint. 0 = total da API.")
_C_STATUS = ("status", "Status", "Código de resposta HTTP (200 ou 500).")
_C_CALLS = ("total", "Chamadas", "Chamadas na semana.")

EXPORT_TABLES: dict[str, dict] = {
    "unique": {
        "table": "unique_consents",
        "label": "Consentimentos únicos",
        "file": "consentimentos-unicos",
        "description": "Total semanal por receptor, com PF e PJ.",
        "columns": _cols(_C_DATE, _C_REC, _C_REC_ID,
                         ("cpf", "Pessoa física", "Consentimentos únicos de pessoas físicas."),
                         ("cnpj", "Pessoa jurídica", "Consentimentos únicos de pessoas jurídicas."),
                         ("total", "Total", "Consentimentos únicos (pessoa física + jurídica).")),
        "filters": {"period", "receptors"},
        "order": "date, receptor_uuid",
        "avg_bytes": 80,
    },
    "active": {
        "table": "active_consents",
        "label": "Consentimentos ativos",
        "file": "consentimentos-ativos",
        "description": "Total semanal por receptor × transmissor.",
        "columns": _cols(_C_DATE, _C_REC, _C_REC_ID, _C_TX, _C_TX_ID,
                         ("total", "Total", "Consentimentos ativos do par receptor × transmissor.")),
        "filters": {"period", "receptors", "transmitters"},
        "order": "date, receptor_uuid, transmitter_uuid",
        "avg_bytes": 116,
    },
    "api": {
        "table": "api_requests",
        "label": "Chamadas de API",
        "file": "chamadas-api",
        "description": "Por receptor × transmissor × API × endpoint × status.",
        "columns": _cols(_C_DATE, _C_REC, _C_REC_ID, _C_TX, _C_TX_ID, _C_API, _C_EP, _C_EP_ID, _C_STATUS, _C_CALLS),
        "filters": {"period", "receptors", "transmitters", "apis", "status", "level"},
        "order": "date, receptor_uuid, transmitter_uuid, api, endpoint_id, status",
        "avg_bytes": 150,
    },
    "pay": {
        "table": "payment_api_requests",
        "label": "Iniciação de pagamento",
        "file": "iniciacao-pagamento",
        "description": "Iniciadora × detentora × API × endpoint × status.",
        "columns": _cols(
            _C_DATE,
            ("receptor", "Iniciadora", "Nome da iniciadora de pagamento."),
            ("receptor_uuid", "ID da iniciadora", "Identificador (UUID) da iniciadora."),
            ("transmitter", "Detentora", "Nome da instituição detentora da conta."),
            ("transmitter_uuid", "ID da detentora", "Identificador (UUID) da detentora."),
            _C_API, _C_EP, _C_EP_ID, _C_STATUS, _C_CALLS),
        "filters": {"period", "receptors", "transmitters", "apis", "status", "level"},
        "order": "date, receptor_uuid, transmitter_uuid, api, endpoint_id, status",
        "avg_bytes": 155,
    },
}

FILTER_LABELS = {
    "period": "Período", "receptors": "Receptores", "transmitters": "Transmissores",
    "apis": "APIs", "status": "Status", "level": "Nível",
}
PAY_FILTER_LABELS = {"receptors": "Iniciadoras", "transmitters": "Detentoras"}


# ── Pedido ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    tables: list[str] = Field(min_length=1, max_length=len(EXPORT_TABLES))
    start: Optional[date] = None
    end: Optional[date] = None
    receptors: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    transmitters: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    apis: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    status: Literal["all", "200", "500"] = "all"
    level: Literal["api", "endpoint"] = "api"

    @field_validator("tables")
    @classmethod
    def _tables(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("Tabela repetida.")
        bad = [t for t in v if t not in EXPORT_TABLES]
        if bad:
            raise ValueError("Tabela não disponível para exportação.")
        return v

    @field_validator("receptors", "transmitters")
    @classmethod
    def _uuids(cls, v: list[str]) -> list[str]:
        if any(not _ID_RE.match(x) for x in v):
            raise ValueError("Identificador de instituição inválido.")
        return v

    @field_validator("apis")
    @classmethod
    def _apis(cls, v: list[str]) -> list[str]:
        if any(not _SLUG_RE.match(x) for x in v):
            raise ValueError("API inválida.")
        return v

    @model_validator(mode="after")
    def _period(self) -> "ExportRequest":
        if self.start and self.end and self.start > self.end:
            raise ValueError("O início do período não pode ser depois do fim.")
        return self


def request_from_query(tables: str, start: str | None, end: str | None, receptors: str | None,
                       transmitters: str | None, apis: str | None, status: str, level: str) -> ExportRequest:
    def lst(s: str | None) -> list[str]:
        return [p.strip() for p in (s or "").split(",") if p.strip()]
    return ExportRequest(tables=lst(tables), start=start or None, end=end or None, receptors=lst(receptors),
                         transmitters=lst(transmitters), apis=lst(apis), status=status, level=level)


# ── Credenciais ───────────────────────────────────────────────────────────────

# Código fixo, decidido pelo dono do produto (2026-11-19). Só o servidor o conhece: a página nunca o
# recebe, e a conferência acontece em `code_matches`. Não protege contra quem souber o código; o
# bloqueio por tentativas só desacelera quem tenta adivinhar.
EXPORT_CODE = "EXPORTAR"


def export_code() -> str:
    return EXPORT_CODE


@lru_cache(maxsize=4)
def _derive(code: str) -> bytes:
    # scrypt: quem capturar um token ou ticket não consegue testar códigos offline na velocidade de um HMAC.
    return hashlib.scrypt(code.encode("utf-8"), salt=SERVER_SALT, n=2 ** 14, r=8, p=1, dklen=32)


def _key() -> bytes:
    return _derive(export_code())


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(kind: str, body: dict, ttl_s: int) -> tuple[str, int]:
    exp = int(time.time()) + ttl_s
    payload = _b64(json.dumps({**body, "exp": exp}, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64(hmac.new(_key(), (kind + "." + payload).encode("ascii"), hashlib.sha256).digest())
    return payload + "." + sig, exp


def verify_token(kind: str, token: str | None) -> dict | None:
    """Corpo do token se a assinatura confere com o código atual e não venceu; senão None."""
    if not token or token.count(".") != 1:
        return None
    payload, sig = token.split(".")
    try:
        want = _b64(hmac.new(_key(), (kind + "." + payload).encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, want):
            return None
        body = json.loads(_unb64(payload))
    except (ValueError, UnicodeError):
        return None
    if not isinstance(body, dict) or int(body.get("exp", 0)) < time.time():
        return None
    return body


def make_session() -> tuple[str, int]:
    return make_token("session", {}, SESSION_TTL_S)


def make_ticket(req: ExportRequest) -> str:
    return make_token("ticket", {"req": req.model_dump(mode="json")}, TICKET_TTL_S)[0]


def request_from_ticket(ticket: str | None) -> ExportRequest | None:
    body = verify_token("ticket", ticket)
    if body is None:
        return None
    try:
        return ExportRequest(**body["req"])
    except Exception:   # ticket assinado com pedido que não valida mais: trata como expirado
        return None


class AttemptLimiter:
    """Erros de código por IP, em memória (por instância)."""

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def blocked(self, ip: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            return self._blocked_until.get(ip, 0) > now

    def fail(self, ip: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            recent = [t for t in self._fails.get(ip, []) if now - t < ATTEMPT_WINDOW_S] + [now]
            self._fails[ip] = recent
            if len(recent) >= ATTEMPT_LIMIT:
                self._blocked_until[ip] = now + BLOCK_S
                self._fails[ip] = []

    def ok(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()
            self._blocked_until.clear()


limiter = AttemptLimiter()


def code_matches(code: str) -> bool:
    want = export_code()
    return hmac.compare_digest(hashlib.sha256(code.encode("utf-8")).digest(),
                               hashlib.sha256(want.encode("utf-8")).digest())


class SlotLease:
    """Um lugar de download. `release` é idempotente, então fim normal, desconexão e tarefa de
    fundo podem chamá-lo todos sem soltar o lugar de outra exportação."""

    def __init__(self, sem: threading.BoundedSemaphore) -> None:
        self._sem: threading.BoundedSemaphore | None = sem
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            sem, self._sem = self._sem, None
        if sem is not None:
            sem.release()


class ExportSlots:
    """No máximo MAX_PARALLEL_EXPORTS downloads ao mesmo tempo por instância."""

    def __init__(self, n: int = MAX_PARALLEL_EXPORTS) -> None:
        self._sem = threading.BoundedSemaphore(n)

    def acquire(self) -> SlotLease | None:
        return SlotLease(self._sem) if self._sem.acquire(blocking=False) else None


slots = ExportSlots()


# ── SQL ───────────────────────────────────────────────────────────────────────

def connect() -> sqlite3.Connection:
    """Conexão somente leitura: a exportação nunca escreve na base."""
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA cache_size = -4096")
    con.execute("PRAGMA mmap_size = 268435456")
    return con


def _db_mtime() -> float:
    try:
        return os.stat(config.DB_PATH).st_mtime
    except OSError:
        return 0.0


def _marks(n: int) -> str:
    return ",".join("?" * n)


def applicable_filters(table_id: str) -> set[str]:
    return EXPORT_TABLES[table_id]["filters"]


def ignored_filters(table_id: str, req: ExportRequest) -> list[str]:
    """Filtros preenchidos que a tabela não aceita (viram "não se aplica" na descrição)."""
    ok = applicable_filters(table_id)
    out = []
    if req.transmitters and "transmitters" not in ok:
        out.append("transmitters")
    if req.apis and "apis" not in ok:
        out.append("apis")
    if req.status != "all" and "status" not in ok:
        out.append("status")
    return out


def build_query(table_id: str, req: ExportRequest, count: bool = False) -> tuple[str, list]:
    """SQL da tabela com os filtros aplicáveis. Nomes só da whitelist; valores por `?`."""
    spec = EXPORT_TABLES[table_id]
    ok = spec["filters"]
    where, params = [], []
    if req.start:
        where.append("date >= ?")
        params.append(req.start.isoformat())
    if req.end:
        where.append("date <= ?")
        params.append(req.end.isoformat())
    if req.receptors:
        where.append(f"receptor_uuid IN ({_marks(len(req.receptors))})")
        params += req.receptors
    if req.transmitters and "transmitters" in ok:
        where.append(f"transmitter_uuid IN ({_marks(len(req.transmitters))})")
        params += req.transmitters
    if req.apis and "apis" in ok:
        where.append(f"api IN ({_marks(len(req.apis))})")
        params += req.apis
    if req.status != "all" and "status" in ok:
        where.append("status = ?")
        params.append(int(req.status))
    if "level" in ok:
        where.append("endpoint_id = 0" if req.level == "api" else "endpoint_id <> 0")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    if count:
        return f"SELECT COUNT(*) FROM {spec['table']}{clause}", params
    cols = ", ".join(c["key"] for c in spec["columns"])
    return f"SELECT {cols} FROM {spec['table']}{clause} ORDER BY {spec['order']}", params


# ── Catálogo (cache por mtime da base) ────────────────────────────────────────

_catalog_cache: TTLCache = TTLCache(maxsize=4, ttl=3600)
_count_cache: TTLCache = TTLCache(maxsize=512, ttl=600)
_catalog_lock = threading.Lock()
_count_lock = threading.Lock()   # TTLCache não é thread-safe


def catalog() -> dict:
    """data_through, primeira/última semana de cada tabela, receptores, transmissores e APIs."""
    key = (str(config.DB_PATH), _db_mtime())
    with _catalog_lock:
        if key in _catalog_cache:
            return _catalog_cache[key]
    con = connect()
    try:
        ranges = {}
        for tid, spec in EXPORT_TABLES.items():
            try:
                lo, hi = con.execute(f"SELECT MIN(date), MAX(date) FROM {spec['table']}").fetchone()
            except sqlite3.OperationalError:     # tabela ainda não gerada: sem dados
                lo = hi = None
            ranges[tid] = {"first_date": lo, "last_date": hi}
        receptors = {}
        for uuid, name in con.execute("SELECT DISTINCT receptor_uuid, receptor FROM unique_consents"):
            receptors[uuid] = name
        try:      # iniciadoras de pagamento que não têm consentimentos únicos
            for uuid, name in con.execute(f"SELECT DISTINCT receptor_uuid, receptor FROM {EXPORT_TABLES['pay']['table']}"):
                receptors.setdefault(uuid, name)
        except sqlite3.OperationalError:
            pass
        tx = {}
        for tid in ("active", "pay"):
            try:
                for uuid, name in con.execute(f"SELECT DISTINCT transmitter_uuid, transmitter FROM {EXPORT_TABLES[tid]['table']}"):
                    tx.setdefault(uuid, name)
            except sqlite3.OperationalError:
                pass
        apis = set()
        for tid in ("pay",):
            try:
                apis |= {r[0] for r in con.execute(f"SELECT DISTINCT api FROM {EXPORT_TABLES[tid]['table']}")}
            except sqlite3.OperationalError:
                pass
    finally:
        con.close()
    from services.constants import API_LABELS
    api_slugs = {**{s: l for s, l in API_LABELS.items()}, "consents": "Consentimentos", "resources": "Recursos"}
    for slug in apis:
        api_slugs.setdefault(slug, slug)
    out = {
        "data_through": ranges["unique"]["last_date"],
        "ranges": ranges,
        "receptors": receptors,
        "transmitters": [{"uuid": u, "label": n} for u, n in sorted(tx.items(), key=lambda kv: kv[1])],
        "apis": [{"slug": s, "label": l} for s, l in sorted(api_slugs.items(), key=lambda kv: kv[1])],
    }
    with _catalog_lock:
        _catalog_cache[key] = out
    return out


def options() -> dict:
    cat = catalog()
    return {
        "data_through": cat["data_through"],
        "tables": [{
            "id": tid, "label": spec["label"], "description": spec["description"],
            "filters": sorted(spec["filters"]), "columns": spec["columns"],
            **cat["ranges"][tid],
        } for tid, spec in EXPORT_TABLES.items()],
        "transmitters": cat["transmitters"],
        "apis": cat["apis"],
    }


def _count_key(req: ExportRequest) -> tuple:
    return (req.model_dump_json(), _db_mtime())


def cached_count(req: ExportRequest) -> dict | None:
    """Contagem já feita para este pedido (sem consultar a base), ou None."""
    with _count_lock:
        return _count_cache.get(_count_key(req))


def count_rows(req: ExportRequest) -> dict:
    cat = catalog()
    key = _count_key(req)
    with _count_lock:
        hit = _count_cache.get(key)
    if hit is not None:
        return hit
    con = connect()
    try:
        tables = []
        for tid in req.tables:
            sql, params = build_query(tid, req, count=True)
            try:
                rows = con.execute(sql, params).fetchone()[0]
            except sqlite3.OperationalError as e:
                if "no such table" not in str(e):     # base travada ou corrompida não vira "0 linhas"
                    raise
                rows = 0
            rng = cat["ranges"][tid]
            lo = max(req.start.isoformat(), rng["first_date"]) if req.start and rng["first_date"] else rng["first_date"]
            hi = min(req.end.isoformat(), rng["last_date"]) if req.end and rng["last_date"] else rng["last_date"]
            tables.append({"id": tid, "rows": rows, "bytes_estimate": rows * EXPORT_TABLES[tid]["avg_bytes"],
                           "period": {"start": lo, "end": hi}, "ignored_filters": ignored_filters(tid, req)})
    finally:
        con.close()
    total = sum(t["rows"] for t in tables)
    out = {"data_through": cat["data_through"], "tables": tables, "total_rows": total,
           "total_bytes_estimate": sum(t["bytes_estimate"] for t in tables), "large": total > LARGE_ROWS}
    with _count_lock:
        _count_cache[key] = out
    return out


# ── Descrição ─────────────────────────────────────────────────────────────────

def _br(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else "—"


def _names(uuids: list[str], lookup: dict[str, str]) -> str:
    if not uuids:
        return "todos"
    names = [lookup.get(u, u) for u in uuids]
    return ", ".join(names[:5]) + (f" e mais {len(names) - 5}" if len(names) > 5 else "")


def describe_filters(table_id: str, req: ExportRequest) -> list[str]:
    """Uma linha por filtro: valor efetivo, ou 'não se aplica'."""
    cat = catalog()
    ok = applicable_filters(table_id)
    rng = cat["ranges"][table_id]
    tx_names = {t["uuid"]: t["label"] for t in cat["transmitters"]}
    lo = req.start.isoformat() if req.start else rng["first_date"]
    hi = req.end.isoformat() if req.end else rng["last_date"]
    pay = table_id == "pay"
    rec_label = PAY_FILTER_LABELS["receptors"] if pay else FILTER_LABELS["receptors"]
    tx_label = PAY_FILTER_LABELS["transmitters"] if pay else FILTER_LABELS["transmitters"]
    lines = [f"Período: {_br(lo)} a {_br(hi)}",
             f"{rec_label}: {_names(req.receptors, cat['receptors'])}",
             f"{tx_label}: " + (_names(req.transmitters, tx_names) if "transmitters" in ok else "não se aplica"),
             "APIs: " + (", ".join(req.apis) if req.apis else "todas") if "apis" in ok else "APIs: não se aplica",
             "Status: " + ({"all": "200 e 500", "200": "200", "500": "500"}[req.status]) if "status" in ok else "Status: não se aplica"]
    if "level" in ok:
        lines.append("Nível: " + ("total por API" if req.level == "api" else "por endpoint"))
    return lines


def file_name(req: ExportRequest) -> str:
    through = catalog()["data_through"] or date.today().isoformat()
    if len(req.tables) == 1:
        return f"opf-dados-{EXPORT_TABLES[req.tables[0]]['file']}-{through}.csv"
    return f"opf-dados-{through}.zip"


# ── Geração ───────────────────────────────────────────────────────────────────

def _csv_chunk(rows: list[tuple]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def iter_csv(table_id: str, req: ExportRequest, comments: bool = True) -> Iterator[bytes]:
    """CSV da tabela em lotes de BATCH_ROWS, com BOM e linhas '#' de descrição."""
    spec = EXPORT_TABLES[table_id]
    sql, params = build_query(table_id, req)
    cat = catalog()
    head = ["﻿" if comments else ""]
    if comments:
        stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        level = ""
        if "level" in spec["filters"]:
            level = " · nível: " + ("total por API" if req.level == "api" else "por endpoint")
        head += [f"# Open Finance Brasil · dados até {_br(cat['data_through'])} · exportado em {stamp}\r\n",
                 f"# Tabela: {spec['label']}{level}\r\n",
                 "# " + " · ".join(describe_filters(table_id, req)) + "\r\n",
                 "# Zeros vieram do portal; semanas sem dado não têm linha.\r\n"]
    labels = [c["label"] for c in spec["columns"]]
    yield ("".join(head)).encode("utf-8") + _csv_chunk([labels])
    con = connect()
    try:
        cur = con.execute(sql, params)
        while True:
            batch = cur.fetchmany(BATCH_ROWS)
            if not batch:
                break
            yield _csv_chunk(batch)
    finally:
        con.close()


class _Sink:
    """Destino sem seek para o zipfile: acumula bytes que o gerador devolve a cada passo."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._pos = 0

    def write(self, b: bytes) -> int:
        self._buf += b
        self._pos += len(b)
        return len(b)

    def tell(self) -> int:
        return self._pos

    def flush(self) -> None:
        pass

    def drain(self) -> bytes:
        out = bytes(self._buf)
        self._buf.clear()
        return out


def readme_text(req: ExportRequest) -> str:
    cat = catalog()
    lines = ["Open Finance Brasil · exportação de dados",
             f"Dados até: {_br(cat['data_through'])}",
             f"Exportado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
             "",
             "Formato: CSV com ';' e vírgula decimal, UTF-8. Valores zero informados pelo portal estão",
             "nos arquivos; semanas sem dado não têm linha.", ""]
    for tid in req.tables:
        spec = EXPORT_TABLES[tid]
        lines += [f"== {spec['label']} ({spec['file']}.csv) =="]
        lines += ["  " + l for l in describe_filters(tid, req)]
        lines += ["  Colunas:"] + [f"    {c['label']}: {c['description']}" for c in spec["columns"]] + [""]
    return "\r\n".join(lines)


def iter_zip(req: ExportRequest) -> Iterator[bytes]:
    """ZIP em streaming: LEIAME.txt e um CSV por tabela (sem linhas '#')."""
    sink = _Sink()
    zf = zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED)   # type: ignore[arg-type]
    with zf.open("LEIAME.txt", "w", force_zip64=True) as m:
        m.write(readme_text(req).encode("utf-8"))
    yield sink.drain()
    for tid in req.tables:
        with zf.open(EXPORT_TABLES[tid]["file"] + ".csv", "w", force_zip64=True) as m:
            first = True
            for chunk in iter_csv(tid, req, comments=False):
                if first:
                    chunk = b"\xef\xbb\xbf" + chunk     # BOM para abrir com acentos no Excel
                    first = False
                m.write(chunk)
                data = sink.drain()
                if data:
                    yield data
        data = sink.drain()
        if data:
            yield data
    zf.close()
    yield sink.drain()
