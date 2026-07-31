"""PostGIS spatial-query routes — real ST_DWithin queries over stored geometries."""

from fastapi import APIRouter, HTTPException, Query

from mapster.services import geodata

router = APIRouter(tags=["geo"])


@router.get("/geo/stats")
def geo_stats():
    return {"rows_per_layer": geodata.counts()}


@router.get("/geo/query")
def geo_query(
    layer: str = Query(..., pattern="^(water|parks|ocean)$"),
    lon: float = Query(...),
    lat: float = Query(...),
    radius_m: float = Query(500, gt=0, le=50000),
):
    gdf = geodata.query_within(layer, lon, lat, radius_m)
    if gdf is None:
        raise HTTPException(status_code=500, detail="Spatial query failed")
    return {
        "layer": layer,
        "count": len(gdf),
        "features": [
            {"city": row.city, "country": row.country, "wkt": row.geometry.wkt}
            for row in gdf.itertuples()
        ],
    }
