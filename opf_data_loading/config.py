"""
config.py — Configuração centralizada
======================================
Expõe constantes de caminho usadas pelos demais módulos.
"""

from pathlib import Path

_BASE_DIR = Path(__file__).parent

DATA_DIR    = _BASE_DIR / "data"
LOG_DIR     = _BASE_DIR / "logs"
DB_PATH     = DATA_DIR / "consents.db"

DEFAULT_WORKERS = 3
