"""
v2_fixtures.py — base SQLite sintética para os testes do Dashboard 2.0 (feature 011).

Duas anos de semanas terminando em 2026-08-28, seis instituições (uma por grupo e
casos de borda): Bradesco (para o "Sempre mostrar" padrão), uma estreante (Shopee),
uma com semana faltando (Belvo) e uma com base minúscula no PJ (Klavi → multiplicador).
O dashboard não importa o data-loader (Princípio V), então o DDL é repetido aqui só
com as colunas lidas.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

END = date(2026, 8, 28)
N_WEEKS = 104
WEEKS = [(END - timedelta(days=7 * (N_WEEKS - 1 - i))).isoformat() for i in range(N_WEEKS)]
GAP_WEEK = WEEKS[N_WEEKS - 4]          # Belvo sem coleta 3 semanas antes do fim
SHOPEE_DEBUT = 80                      # índice da semana de estreia

INSTITUTIONS = {
    # uuid: (nome na base, grupo esperado)
    "rec-nu":    ("NUBANK", "neo_banks"),
    "rec-belvo": ("BELVO IP", "itps"),
    "rec-sant":  ("SANTANDER BRASIL", "incumbentes"),
    "rec-klavi": ("KLAVI INSTITUICAO DE PAGAMENTO", "itps"),
    "rec-brad":  ("BRADESCO", "incumbentes"),
    "rec-shop":  ("SHOPEE", "outros"),
}


def cpf(uuid: str, i: int) -> int | None:
    if uuid == "rec-nu":
        return 5_000_000 + 30_000 * i
    if uuid == "rec-belvo":
        return None if WEEKS[i] == GAP_WEEK else 3_000_000 + 20_000 * i
    if uuid == "rec-sant":
        return 2_500_000 + 5_000 * i
    if uuid == "rec-klavi":
        return 2_000_000
    if uuid == "rec-brad":
        return 1_000_000 + 10_000 * i
    if uuid == "rec-shop":
        return None if i < SHOPEE_DEBUT else 100_000 * (i - SHOPEE_DEBUT + 1)
    raise KeyError(uuid)


def cnpj(uuid: str, i: int) -> int:
    if uuid == "rec-klavi":
        return 300 + 300 * i          # 300 → ~31 mil: base minúscula, vira multiplicador
    return 50_000 + 1_000 * i


DDL = """
CREATE TABLE unique_consents (
    date TEXT NOT NULL, receptor TEXT NOT NULL, receptor_uuid TEXT NOT NULL DEFAULT '',
    cpf INTEGER NOT NULL DEFAULT 0, cnpj INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL DEFAULT '', PRIMARY KEY (date, receptor_uuid)
);
CREATE TABLE active_consents (
    receptor_uuid TEXT NOT NULL, transmitter_uuid TEXT NOT NULL, receptor TEXT NOT NULL DEFAULT '',
    transmitter TEXT NOT NULL DEFAULT '', date TEXT NOT NULL, total INTEGER NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT '', PRIMARY KEY (receptor_uuid, transmitter_uuid, date)
);
CREATE TABLE api_requests (
    receptor_uuid TEXT, receptor TEXT, transmitter_uuid TEXT, transmitter TEXT,
    api TEXT, endpoint_id INTEGER, endpoint TEXT, status INTEGER, date TEXT, total INTEGER DEFAULT 0
);
CREATE TABLE api_group_weekly (
    date TEXT, receptor_uuid TEXT, receptor TEXT, grp TEXT,
    req_week INTEGER DEFAULT 0, consents_total INTEGER DEFAULT 0, PRIMARY KEY (date, receptor_uuid, grp)
);
CREATE TABLE behavior_signals (
    week TEXT, signal_type TEXT, metric TEXT, api_group TEXT DEFAULT '', receptor_uuid TEXT,
    receptor TEXT, value_prev REAL, value_curr REAL, change_pct REAL, volume INTEGER DEFAULT 0
);
CREATE TABLE behavior_signals_run (
    id INTEGER PRIMARY KEY, computed_at TEXT, consents_through TEXT, api_through TEXT,
    api_skipped_weeks TEXT DEFAULT '[]', signals_total INTEGER DEFAULT 0
);
CREATE TABLE fetch_attempts (run_id TEXT, phase TEXT, target TEXT, started_at TEXT, duration_ms INTEGER,
    status TEXT, records_count INTEGER, error_class TEXT, error_msg TEXT);
CREATE TABLE run_summary (run_id TEXT PRIMARY KEY);
"""

DDL_STATUS = """
CREATE TABLE api_status_weekly (
    date TEXT NOT NULL, receptor_uuid TEXT NOT NULL, receptor TEXT NOT NULL DEFAULT '',
    transmitter_uuid TEXT NOT NULL DEFAULT '', transmitter TEXT NOT NULL DEFAULT '',
    status INTEGER NOT NULL, total INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, receptor_uuid, transmitter_uuid, status)
);
"""


def calls_ok(uuid: str, i: int) -> int | None:
    v = cpf(uuid, i)
    return None if v is None else 2 * v


def calls_err(uuid: str, i: int) -> int | None:
    ok = calls_ok(uuid, i)
    if ok is None:
        return None
    return ok // 20 if uuid == "rec-nu" else ok // 10   # Nubank 5%/105, demais 10%/110


def build_db(path: Path, with_status_table: bool = True) -> Path:
    con = sqlite3.connect(str(path))
    con.executescript(DDL + (DDL_STATUS if with_status_table else ""))
    for i, week in enumerate(WEEKS):
        for uuid, (name, _grp) in INSTITUTIONS.items():
            pf = cpf(uuid, i)
            if pf is None:
                continue
            pj = cnpj(uuid, i)
            con.execute("INSERT INTO unique_consents (date, receptor, receptor_uuid, cpf, cnpj, total) "
                        "VALUES (?,?,?,?,?,?)", (week, name, uuid, pf, pj, pf + pj))
            con.execute("INSERT INTO active_consents (receptor_uuid, transmitter_uuid, receptor, transmitter, date, total) "
                        "VALUES (?,?,?,?,?,?)", (uuid, "txm-1", name, "ITAÚ UNIBANCO", week, int(pf * 1.7)))
            ok, err = calls_ok(uuid, i), calls_err(uuid, i)
            con.execute("INSERT INTO api_group_weekly (date, receptor_uuid, receptor, grp, req_week, consents_total) "
                        "VALUES (?,?,?,?,?,?)", (week, uuid, name, "Conta", ok, pf + pj))
            if with_status_table:
                for status, total in ((200, ok), (500, err)):
                    con.execute("INSERT INTO api_status_weekly (date, receptor_uuid, receptor, transmitter_uuid, "
                                "transmitter, status, total) VALUES (?,?,?,?,?,?,?)",
                                (week, uuid, name, "txm-1", "ITAÚ UNIBANCO", status, total))
    con.execute("INSERT INTO behavior_signals_run (id, computed_at, consents_through, api_through) "
                "VALUES (1, '2026-09-23T10:00:00Z', ?, ?)", (END.isoformat(), END.isoformat()))
    con.commit()
    con.close()
    return path
