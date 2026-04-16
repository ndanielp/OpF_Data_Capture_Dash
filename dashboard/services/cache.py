import os
from cachetools import TTLCache

_cache: TTLCache | None = None

def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        ttl = int(os.environ.get("OF_CACHE_TTL_SECONDS", 3600))
        _cache = TTLCache(maxsize=128, ttl=ttl)
    return _cache
