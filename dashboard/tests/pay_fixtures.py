"""
pay_fixtures.py — base SQLite sintética do tema Pagamentos (feature 018).

10 semanas terminando em 2026-10-30: agosto com 1 semana, setembro com 4, outubro com 5 (a
normalização mensal tem de deixar os três iguais quando a semana é igual). Cenários:
- Iniciador → Itaú, Pagamento Automático constante (10 mil/semana, 1 mil falhas).
- Iniciador → Nubank, Automático (5 mil/semana, 500 falhas).
- Iniciador → Bradesco, Automático 10 mil/semana e 20 mil na última: alta só na última semana
  (Bradesco detentora fica "em observação").
- Google Pay → Santander, Iniciação 20 mil/semana; falha 0 até a semana 5 e 5 mil a partir da 6:
  falha confirmada em duas semanas (alerta). Consultas (66) = 2 por iniciação.
- Nubank → Itaú, Automático 3 mil/semana (Nubank nos dois papéis).
- Vínculos (Google Pay → Nubank): 133=1000, 139=990, 136=500, 137=480, 135=20 por semana.
O dashboard não importa o data-loader (Princípio V): o DDL é repetido aqui.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

END = date(2026, 10, 30)
N_WEEKS = 10
WEEKS = [(END - timedelta(days=7 * (N_WEEKS - 1 - i))).isoformat() for i in range(N_WEEKS)]

NAMES = {
    "ini-a": "INICIADOR",
    "ini-g": "GOOGLE PAY BRASIL INSTITUICAO DE PAGAMENTO LTDA.",
    "ini-n": "NUBANK",
    "det-i": "ITAÚ UNIBANCO",
    "det-b": "BRADESCO",
    "det-s": "SANTANDER BRASIL",
}

DDL_PAYMENTS = """
CREATE TABLE payment_weekly (
    date TEXT NOT NULL, receptor_uuid TEXT NOT NULL, receptor TEXT NOT NULL DEFAULT '',
    transmitter_uuid TEXT NOT NULL, transmitter TEXT NOT NULL DEFAULT '', api TEXT NOT NULL,
    endpoint_id INTEGER NOT NULL, status INTEGER NOT NULL, total INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, receptor_uuid, transmitter_uuid, endpoint_id, status)
);
"""
DDL_CONSENTS = """
CREATE TABLE unique_consents (
    date TEXT NOT NULL, receptor TEXT NOT NULL, receptor_uuid TEXT NOT NULL DEFAULT '',
    cpf INTEGER NOT NULL DEFAULT 0, cnpj INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL DEFAULT '', PRIMARY KEY (date, receptor_uuid)
);
"""

_API = {65: "payments", 66: "payments", 129: "automatic-payments", 130: "automatic-payments"}


def rows() -> list[tuple]:
    out = []

    def add(i: int, r: str, t: str, ep: int, total: int, status: int = 200) -> None:
        if total:
            out.append((WEEKS[i], r, NAMES[r], t, NAMES[t], _API.get(ep, "enrollments"), ep, status, total))

    for i in range(N_WEEKS):
        add(i, "ini-a", "det-i", 129, 10_000)
        add(i, "ini-a", "det-i", 129, 1_000, 500)
        add(i, "ini-a", "ini-n", 129, 5_000)
        add(i, "ini-a", "ini-n", 129, 500, 500)
        add(i, "ini-a", "det-b", 129, 20_000 if i == N_WEEKS - 1 else 10_000)
        add(i, "ini-g", "det-s", 65, 20_000)
        add(i, "ini-g", "det-s", 65, 5_000 if i >= 6 else 0, 500)
        add(i, "ini-g", "det-s", 66, 40_000)
        add(i, "ini-n", "det-i", 129, 3_000)
        for ep, v in ((133, 1_000), (139, 990), (136, 500), (137, 480), (135, 20)):
            add(i, "ini-g", "ini-n", ep, v)
    return out


def build_db(path: Path, with_payments: bool = True) -> Path:
    con = sqlite3.connect(path)
    con.executescript((DDL_PAYMENTS if with_payments else "") + DDL_CONSENTS)
    if with_payments:
        con.executemany("INSERT INTO payment_weekly VALUES (?,?,?,?,?,?,?,?,?)", rows())
    con.executemany("INSERT INTO unique_consents (date, receptor, receptor_uuid, cpf, cnpj, total) VALUES (?,?,?,?,?,?)",
                    [(w, "NUBANK", "ini-n", 100, 0, 100) for w in WEEKS])
    con.commit()
    con.close()
    return path
