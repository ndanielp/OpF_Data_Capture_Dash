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

DEFAULT_WORKERS = 4

# Quando True, scrapers usam OpFSession (POST direto via page.request.post).
# Flag existe para fallback ao modo antigo (route + click) durante transição.
USE_HTTP_DIRECT = True

# Cache de metadata (discovery de APIs/endpoints) — TTL em segundos.
META_CACHE_PATH = DATA_DIR / "_meta_cache.json"
META_CACHE_TTL  = 24 * 60 * 60
