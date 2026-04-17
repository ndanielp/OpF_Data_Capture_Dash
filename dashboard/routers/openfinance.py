from fastapi import APIRouter, HTTPException, Query
from services.cache import get_cache
from services.constants import API_GROUPS, BRAND_COLORS
import services.of_analytics as of_analytics
from typing import Optional

router = APIRouter()


@router.get("/brand-colors")
def brand_colors():
    """Canonical brand colors for top institutions. Single source of truth
    consumed by both Ecossistema and Perfil Receptor so avatars, chart
    series and legends match across tabs."""
    return {"brands": [{"match": m, "color": c} for m, c in BRAND_COLORS]}


@router.get("/api-groups")
def api_groups():
    """Canonical API group definitions (display label → color + apis).
    Frontend uses this to label charts and color chips so there is no
    drift between backend and UI."""
    return {"groups": API_GROUPS}

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

@router.get("/receptor-profile/header")
def receptor_header(
    institution: str = Query(...),
    from_date: Optional[str] = Query("2000-01-01", alias="from"),
    to_date:   Optional[str] = Query("2100-01-01", alias="to"),
):
    cache = get_cache()
    key = f"header:{institution}:{from_date}:{to_date}"
    if key not in cache:
        try:
            result = of_analytics.get_profile_header(institution, from_date, to_date)
            if not result:
                raise HTTPException(status_code=404, detail=f"Institution '{institution}' not found or no data in period")
            cache[key] = result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[key]

@router.get("/receptor-profile/strategic-map")
def receptor_strategic_map(
    from_date: Optional[str] = Query("2000-01-01", alias="from"),
    to_date:   Optional[str] = Query("2100-01-01", alias="to"),
):
    cache = get_cache()
    key = f"smap:{from_date}:{to_date}"
    if key not in cache:
        try:
            cache[key] = of_analytics._get_strategic_map(from_date, to_date)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[key]

@router.get("/receptor-profile/temporal")
def receptor_temporal(
    institution: str = Query(...),
    from_date: Optional[str] = Query("2000-01-01", alias="from"),
    to_date:   Optional[str] = Query("2100-01-01", alias="to"),
):
    cache = get_cache()
    key = f"temporal:{institution}:{from_date}:{to_date}"
    if key not in cache:
        try:
            cache[key] = of_analytics.get_temporal_intensity(institution, from_date, to_date)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[key]

@router.get("/receptor-profile/tornado")
def receptor_tornado(
    institution: str = Query(...),
    from_date: Optional[str] = Query("2000-01-01", alias="from"),
    to_date:   Optional[str] = Query("2100-01-01", alias="to"),
):
    cache = get_cache()
    key = f"tornado:{institution}:{from_date}:{to_date}"
    if key not in cache:
        try:
            cache[key] = of_analytics.get_tornado_data(institution, from_date, to_date)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[key]

@router.get("/receptor-profile/depth")
def receptor_depth(
    institution: str = Query(...),
    from_date: Optional[str] = Query("2000-01-01", alias="from"),
    to_date:   Optional[str] = Query("2100-01-01", alias="to"),
):
    cache = get_cache()
    key = f"depth:{institution}:{from_date}:{to_date}"
    if key not in cache:
        try:
            cache[key] = of_analytics.get_endpoint_depth(institution, from_date, to_date)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return cache[key]
