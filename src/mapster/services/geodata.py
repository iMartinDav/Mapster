"""PostGIS-backed spatial storage for fetched OSM geometries (water/parks/ocean).

This is a genuine spatial-database tier on top of Neon: GeoPandas
(.to_postgis / .read_postgis) handles geometry (de)serialization via GDAL
(through pyogrio) and GeoAlchemy2 supplies the PostGIS Geometry column type
for SQLAlchemy. It exists so map geometries are queryable with real spatial
SQL (ST_DWithin, ST_Intersects, ...) instead of only being opaque cache
blobs — it is an additional, best-effort tier alongside the pickled disk/
Neon preview cache, not a replacement for it.
"""

from typing import Optional

import geopandas as gpd
from sqlalchemy import text

from mapster.db import get_engine

LAYER_TABLES = {
    "water": "geo_water",
    "parks": "geo_parks",
    "ocean": "geo_ocean",
    "roads": "geo_roads",
}


def _ensure_srid_4326(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        return gdf.set_crs(epsg=4326)
    if gdf.crs.to_epsg() != 4326:
        return gdf.to_crs(epsg=4326)
    return gdf


def _write_layer(table: str, city: str, country: str, cache_hash: str, gdf: gpd.GeoDataFrame, extra_cols=None) -> int:
    if gdf is None or len(gdf) == 0:
        return 0

    cols_to_keep = ["geometry"]
    if extra_cols:
        for col in extra_cols:
            if col in gdf.columns:
                cols_to_keep.append(col)

    out = gdf[cols_to_keep].copy()
    out = _ensure_srid_4326(out)
    out["city"] = city
    out["country"] = country
    out["cache_key"] = cache_hash
    
    # Handle list types (like highway) for PostGIS compatibility
    for col in out.columns:
        if out[col].apply(lambda x: isinstance(x, list)).any():
            out[col] = out[col].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else x)

    engine = get_engine()
    out.to_postgis(table, engine, if_exists="append", index=False)

    # Best-effort spatial index (idempotent)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {table}_geom_idx ON {table} USING GIST (geometry)"))
    except Exception:
        pass

    return len(out)


class PostgisGeoStore:
    """Duck-typed backend for MapPosterGenerator's geo caching."""

    def save(self, city: str, country: str, cache_hash: str, water, parks, ocean, roads=None) -> dict:
        counts = {}
        if water is not None:
            counts["water"] = _write_layer(LAYER_TABLES["water"], city, country, cache_hash, water)
        if parks is not None:
            counts["parks"] = _write_layer(LAYER_TABLES["parks"], city, country, cache_hash, parks)
        if ocean is not None:
            counts["ocean"] = _write_layer(LAYER_TABLES["ocean"], city, country, cache_hash, ocean)
        if roads is not None:
            # For roads, we want to keep the 'highway' column for styling
            counts["roads"] = _write_layer(LAYER_TABLES["roads"], city, country, cache_hash, roads, extra_cols=["highway"])
        return counts

    def load(self, lon: float, lat: float, radius_m: float):
        """Load geometries for a given point and radius from PostGIS using ST_DWithin.
        Returns a tuple: (roads, water, parks, ocean) as GeoDataFrames.
        If the data doesn't exist for the coverage area, returns (None, None, None, None).
        """
        # We query the bounding box first to ensure we have cached data covering this area
        engine = get_engine()
        with engine.connect() as conn:
            # Fast check: does geo_water or geo_roads exist and have points nearby?
            # A true production GIS would track fetched bounding boxes (coverage polygons),
            # but here we rely on checking if ST_DWithin returns enough results.
            pass
            
        roads = query_within("roads", lon, lat, radius_m)
        if roads is None or len(roads) == 0:
            return None, None, None, None  # Cache miss
            
        water = query_within("water", lon, lat, radius_m)
        parks = query_within("parks", lon, lat, radius_m)
        ocean = query_within("ocean", lon, lat, radius_m)
        
        return roads, water, parks, ocean


def query_within(layer: str, lon: float, lat: float, radius_m: float, limit: int = 50000) -> Optional[gpd.GeoDataFrame]:
    """Spatial query: geometries of `layer` within radius_m meters of (lon, lat)."""
    table = LAYER_TABLES.get(layer)
    if table is None:
        return None
    engine = get_engine()
    
    # Check if table exists first to avoid crashing
    try:
        with engine.connect() as conn:
            exists = conn.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")).scalar()
            if not exists:
                return None
    except Exception:
        return None

    sql = text(f"""
        SELECT *
        FROM {table}
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        LIMIT :limit
    """)
    try:
        return gpd.read_postgis(sql, engine, geom_col="geometry", params={"lon": lon, "lat": lat, "radius": radius_m, "limit": limit})
    except Exception as e:
        print(f"PostGIS query failed for {table}: {e}")
        return None


def counts() -> dict:
    """Row counts per layer table — used by the /geo/stats endpoint."""
    engine = get_engine()
    result = {}
    with engine.connect() as conn:
        for layer, table in LAYER_TABLES.items():
            try:
                result[layer] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            except Exception:
                result[layer] = 0
    return result
