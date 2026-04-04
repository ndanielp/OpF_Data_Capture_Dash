"""
config.py — Configuração centralizada
======================================
Lê variáveis de ambiente (via .env) e expõe constantes usadas pelos demais módulos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega .env se existir (sem sobrescrever variáveis já definidas no ambiente)
load_dotenv(override=False)

# ── Google Drive ───────────────────────────────────────────────────────────────
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
SERVICE_ACCOUNT_FILE = Path(
    os.getenv("SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
)

# ── Caminhos locais ────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent
LOCAL_LOG_DIR = _BASE_DIR / os.getenv("LOCAL_LOG_DIR", "logs")
DB_PATH = _BASE_DIR / os.getenv("DB_PATH", "data/consents.db")

# ── Coleta ─────────────────────────────────────────────────────────────────────
DEFAULT_WORKERS = int(os.getenv("DEFAULT_WORKERS", "3"))
