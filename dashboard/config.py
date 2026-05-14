"""
config.py — Configuração centralizada
======================================
Expõe constantes de caminho usadas pelos demais módulos.

DB_PATH resolution order:
  1. Env var OPF_DB_PATH (override explícito)
  2. ../data-loader/data/consents.db    (dev local — fonte única do loader)
  3. ./data/consents.db                 (Docker/Cloud Run — baixado pelo entrypoint do GCS)
"""

import os
from pathlib import Path

_BASE_DIR = Path(__file__).parent

LOG_DIR  = _BASE_DIR / "logs"

_LOADER_DB = _BASE_DIR.parent / "data-loader" / "data" / "consents.db"
_LOCAL_DB  = _BASE_DIR / "data" / "consents.db"

if os.environ.get("OPF_DB_PATH"):
    DB_PATH = Path(os.environ["OPF_DB_PATH"])
elif _LOADER_DB.exists():
    DB_PATH = _LOADER_DB
else:
    DB_PATH = _LOCAL_DB

DATA_DIR = DB_PATH.parent
