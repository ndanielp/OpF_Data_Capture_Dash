from fastapi import APIRouter, HTTPException, Query
from services.cache import get_cache
import services.of_analytics as of_analytics
from typing import Optional

router = APIRouter()

@router.get("/institutions")
def institutions():
    cache = get_cache()
    if "institutions" not in cache:
        try:
            cache["institutions"] = {"institutions": of_analytics.get_institutions()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache["institutions"]

@router.get("/ecosystem-stats")
def ecosystem_stats():
    cache = get_cache()
    if "ecosystem_stats" not in cache:
        try:
            cache["ecosystem_stats"] = of_analytics.get_ecosystem_stats()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache["ecosystem_stats"]

@router.get("/receptor-profile")
def receptor_profile(institution: str = Query(...), from_date: Optional[str] = Query("2000-01-01", alias="from"), to_date: Optional[str] = Query("2100-01-01", alias="to")):
    cache = get_cache()
    cache_key = f"profile:{institution}:{from_date}:{to_date}"
    if cache_key not in cache:
        try:
            profile = of_analytics.get_receptor_profile(institution, from_date, to_date)
            if not profile:
                raise HTTPException(status_code=404, detail=f"Institution '{institution}' not found or no data in period")
            cache[cache_key] = profile
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[cache_key]
