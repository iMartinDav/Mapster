import gc
import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.colors as mcolors
import numpy as np
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import json
import os
from datetime import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pickle
import hashlib
import gzip
from collections import OrderedDict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class MapPosterGenerator:
    MAP_FORMATS = {
        "poster_vertical": {"width": 12, "height": 16, "dpi": 300, "view_width": 1000, "view_height": 1333, "name": "Poster (Vertical)"},
        "poster_horizontal": {"width": 16, "height": 12, "dpi": 300, "view_width": 1333, "view_height": 1000, "name": "Poster (Horizontal)"},
        "desktop": {"width": 19.2, "height": 10.8, "dpi": 200, "view_width": 1920, "view_height": 1080, "name": "Desktop Wallpaper (16:9)"},
        "phone": {"width": 10.8, "height": 19.2, "dpi": 200, "view_width": 1080, "view_height": 1920, "name": "Phone Wallpaper (9:16)"}
    }
    def __init__(self, base_dir=".", remote_cache=None, history_hook=None, geo_store=None):
        self.base_dir = base_dir
        self.themes_dir = os.path.join(base_dir, "themes")
        self.fonts_dir = os.path.join(base_dir, "fonts")
        self.posters_dir = os.path.join(base_dir, "posters")
        self.cache_dir = os.path.join(base_dir, "cache")
        self.fonts = self._load_fonts()

        # Optional remote cache backend (duck-typed: .get(key) / .set(key, data)).
        # Used as an L2 tier behind the local disk cache; the engine itself stays
        # storage-agnostic. Passing None (default) disables the remote tier.
        self.remote_cache = remote_cache

        # Optional callback invoked with a metadata dict whenever a preview or
        # poster is saved, so callers can persist durable history elsewhere.
        self.history_hook = history_hook

        # Optional PostGIS-backed spatial store (duck-typed: .save(city, country,
        # cache_hash, water_gdf, parks_gdf, ocean_gdf)). Best-effort, backgrounded —
        # never blocks or fails map generation if the spatial DB is slow/down.
        self.geo_store = geo_store

        # Optimize OSMnx settings
        ox.settings.use_cache = True
        ox.settings.log_console = False
        ox.settings.timeout = 180 # Increase timeout for large residential queries

        # Ensure directories exist (still needed for local fallback and temp files)
        os.makedirs(self.posters_dir, exist_ok=True)
        os.makedirs(self.themes_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.data_cache = OrderedDict()
        self._ocean_gdf = None  # Lazy-loaded Natural Earth ocean shapefile
        
        # Thread pool for background cloud uploads (prevents daemon thread data loss)
        self._upload_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cloud-upload")

    def _load_ocean_shapefile(self):
        """Load Natural Earth ocean shapefile (lazy, cached in memory). Used as fallback."""
        if self._ocean_gdf is not None:
            return self._ocean_gdf

        ocean_path = os.path.join(self.base_dir, "data", "ne_10m_ocean.shp")
        if not os.path.exists(ocean_path):
            print("Warning: Ocean shapefile not found at", ocean_path)
            return None

        import geopandas as gpd
        self._ocean_gdf = gpd.read_file(ocean_path)
        print(f"Loaded ocean shapefile: {len(self._ocean_gdf)} features")
        return self._ocean_gdf

    def _get_ocean_for_bbox(self, point, distance):
        """Get ocean polygon for the map's bounding box.

        Uses OSM coastline data for detailed geometry, with Natural Earth 10m
        as a classifier to identify which polygonized regions are ocean.
        Falls back to Natural Earth alone if coastline data is unavailable.
        Returns a GeoDataFrame of ocean polygons, or None for inland cities.
        """
        import geopandas as gpd
        from shapely.geometry import box, Point, Polygon, MultiLineString, LineString
        from shapely.ops import linemerge, unary_union, polygonize
        import math

        lat, lon = point
        cos_lat = math.cos(math.radians(lat))

        # Bounding box with 1.5x buffer for all format aspect ratios
        span_meters = distance * 2.0
        height_deg = span_meters / 111320.0
        width_deg = height_deg / cos_lat
        buf = 1.5
        bbox_poly = box(
            lon - width_deg * buf, lat - height_deg * buf,
            lon + width_deg * buf, lat + height_deg * buf
        )

        # --- Step 1: Get Natural Earth ocean for this bbox (rough classifier) ---
        ocean_gdf = self._load_ocean_shapefile()
        ne_ocean = None
        if ocean_gdf is not None:
            try:
                ne_clipped = gpd.clip(ocean_gdf, bbox_poly)
                if ne_clipped is not None and not ne_clipped.empty:
                    ne_ocean = unary_union(ne_clipped.geometry)
            except Exception:
                pass

        if ne_ocean is None or ne_ocean.is_empty:
            return None  # Inland city — no ocean nearby

        # --- Step 2: Try OSM coastline for detailed geometry ---
        try:
            coast_gdf = ox.features_from_point(
                point, tags={'natural': 'coastline'}, dist=int(distance * 2)
            )
            lines = [g for g in coast_gdf.geometry if g.geom_type == 'LineString']

            if len(lines) > 0:
                merged = linemerge(MultiLineString(lines))
                merged_lines = list(merged.geoms) if merged.geom_type == 'MultiLineString' else [merged]

                # Clip to bbox and snap open endpoints to bbox boundary
                bbox_ring = bbox_poly.exterior
                snapped_lines = []
                for line in merged_lines:
                    inter = line.intersection(bbox_poly)
                    if inter.is_empty:
                        continue
                    sub_lines = [inter] if inter.geom_type == 'LineString' else list(inter.geoms)
                    for sub in sub_lines:
                        if sub.is_ring:
                            snapped_lines.append(sub)
                            continue
                        coords = list(sub.coords)
                        if len(coords) < 2:
                            continue
                        start_snap = bbox_ring.interpolate(bbox_ring.project(Point(coords[0])))
                        end_snap = bbox_ring.interpolate(bbox_ring.project(Point(coords[-1])))
                        extended = [(start_snap.x, start_snap.y)] + coords + [(end_snap.x, end_snap.y)]
                        snapped_lines.append(LineString(extended))

                if snapped_lines:
                    # Polygonize: coastlines + bbox boundary → many small polygons
                    all_lines = unary_union(snapped_lines + [bbox_ring])
                    polys = list(polygonize(all_lines))

                    if polys:
                        # Classify each polygon: ocean if >50% overlaps with NE ocean
                        ocean_polys = []
                        land_polys = []
                        for p in polys:
                            if p.area < 1e-8:
                                continue
                            overlap = p.intersection(ne_ocean).area / p.area
                            if overlap > 0.5:
                                ocean_polys.append(p)
                            else:
                                land_polys.append(p)

                        if ocean_polys:
                            ocean_union = unary_union(ocean_polys)

                            # Subtract island land polygons from ocean to create holes.
                            # Islands are land polys fully contained within the ocean area.
                            # Without this, bays (e.g. Guanabara Bay) cover islands like
                            # Ilha do Governador because polygonize doesn't nest holes.
                            # Batch all islands into one geometry for a single difference()
                            # instead of O(n) separate operations.
                            if land_polys:
                                buffered = ocean_union.buffer(0.0001)
                                islands = [lp for lp in land_polys
                                           if ocean_union.contains(lp) or buffered.contains(lp)]
                                if islands:
                                    island_union = unary_union(islands)
                                    ocean_union = ocean_union.difference(island_union)
                            # Clip to bbox to remove any overshoot
                            ocean_union = ocean_union.intersection(bbox_poly)
                            if not ocean_union.is_empty:
                                geoms = list(ocean_union.geoms) if ocean_union.geom_type == 'MultiPolygon' else [ocean_union]
                                result = gpd.GeoDataFrame(geometry=geoms, crs='EPSG:4326')
                                v_count = sum(
                                    len(g.exterior.coords) + sum(len(r.coords) for r in g.interiors)
                                    for g in geoms if g.geom_type == 'Polygon'
                                )
                                print(f"Ocean from OSM coastline: {v_count} vertices, {len(geoms)} polygons")
                                return result

            print("OSM coastline processing failed, using Natural Earth fallback")
        except Exception as e:
            print(f"OSM coastline fetch failed ({e}), using Natural Earth fallback")

        # --- Fallback: Natural Earth only ---
        try:
            ne_clipped = gpd.clip(ocean_gdf, bbox_poly)
            if ne_clipped is not None and not ne_clipped.empty:
                print("Ocean from Natural Earth fallback")
                return ne_clipped
        except Exception as e:
            print(f"Warning: Ocean clipping failed: {e}")
        return None

    def clear_memory_cache(self):
        """Clear in-memory caches to free RAM. Disk + remote caches remain available."""
        self.data_cache.clear()

    def trim_memory_cache(self, max_entries=3):
        """Evict oldest entries from memory cache, keeping the most recent N.

        This is preferred over clear_memory_cache() because it keeps recent
        data in memory for fast repeat access (e.g., preview→generate flow)
        while bounding memory usage.
        """
        while len(self.data_cache) > max_entries:
            self.data_cache.popitem(last=False)  # Remove oldest entry

        # When trimming aggressively (before new jobs), also release ocean shapefile
        # to free ~15-30MB. It will be reloaded on next coastal city request.
        if max_entries <= 2:
            self._ocean_gdf = None

    def _get_cache_key_hash(self, cache_key):
        """Generate a hash string from cache key for filename."""
        # Convert cache key to string and hash it
        key_str = str(cache_key)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_filepath(self, cache_key):
        """Generate filepath for cache based on cache key."""
        cache_hash = self._get_cache_key_hash(cache_key)
        return os.path.join(self.cache_dir, f"{cache_hash}.pkl")
    
    def _save_cache_to_disk(self, cache_key, data):
        """Save to local disk (fast, synchronous) and cloud (background, non-blocking)."""
        # Local disk save — synchronous, fast (~1s)
        try:
            filepath = self._get_cache_filepath(cache_key)
            with gzip.open(filepath, 'wb', compresslevel=1) as f:
                pickle.dump(data, f)
            print(f"Cache saved to disk: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"Warning: Failed to save cache to disk: {e}")

        # Remote save — background executor, non-blocking
        # The caller doesn't need to wait for the remote-cache write.
        # Using executor instead of daemon threads prevents data loss on shutdown
        if self.remote_cache:
            self._upload_executor.submit(self._upload_cache_to_remote, cache_key, data)

    def _upload_cache_to_remote(self, cache_key, data):
        """Background write to the remote cache tier. Fire-and-forget."""
        try:
            self.remote_cache.set(cache_key, data)
        except Exception as e:
            print(f"[bg] Warning: Remote cache save failed: {e}")

    def _save_geo_to_postgis(self, city, country, cache_hash, water, parks, ocean, G=None):
        """Background write of real geometries to PostGIS. Fire-and-forget."""
        try:
            roads_gdf = None
            if G is not None:
                if isinstance(G, gpd.GeoDataFrame):
                    roads_gdf = G
                elif len(G.edges) > 0:
                    import osmnx as ox
                    # Ensure CRS exists
                    if not hasattr(G.graph, 'get') or 'crs' not in G.graph:
                        G.graph['crs'] = 'EPSG:4326'
                    roads_gdf = ox.graph_to_gdfs(G, nodes=False)
                    
            self.geo_store.save(city or "", country or "", cache_hash, water, parks, ocean, roads=roads_gdf)
        except Exception as e:
            print(f"[bg] Warning: PostGIS geo store failed: {e}")

    def _load_cache_from_disk(self, cache_key):
        """Load processed map data from storage (local disk first, then remote)."""
        # Try local disk first (faster for local dev)
        try:
            filepath = self._get_cache_filepath(cache_key)
            if os.path.exists(filepath):
                # Try gzip first (new compressed format), fall back to raw pickle (legacy)
                try:
                    with gzip.open(filepath, 'rb') as f:
                        data = pickle.load(f)
                except (gzip.BadGzipFile, OSError):
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                print(f"Cache loaded from disk: {os.path.basename(filepath)}")
                return data
        except Exception as e:
            print(f"Warning: Failed to load cache from disk: {e}")

        # Fall back to the remote cache tier
        if self.remote_cache:
            try:
                data = self.remote_cache.get(cache_key)
                if data is not None:
                    print("Cache loaded from remote tier")
                    return data
            except Exception as e:
                print(f"Remote cache load failed: {e}")

        return None

    def _load_fonts(self):
        """Load fonts from the fonts directory."""
        fonts = {
            'bold': os.path.join(self.fonts_dir, 'Roboto-Bold.ttf'),
            'regular': os.path.join(self.fonts_dir, 'Roboto-Regular.ttf'),
            'light': os.path.join(self.fonts_dir, 'Roboto-Light.ttf')
        }
        # Check if fonts exist, otherwise return None to use system defaults
        for path in fonts.values():
            if not os.path.exists(path):
                return None
        return fonts

    def get_available_themes(self):
        """Return a list of available theme names."""
        if not os.path.exists(self.themes_dir):
            return []
        
        themes = []
        for file in sorted(os.listdir(self.themes_dir)):
            if file.endswith('.json'):
                themes.append(file[:-5])
        return themes

    def load_theme(self, theme_name="feature_based"):
        """Load functionality for a specific theme."""
        theme_file = os.path.join(self.themes_dir, f"{theme_name}.json")
        default_theme = {
            "name": "Feature-Based Shading",
            "bg": "#FFFFFF",
            "text": "#000000",
            "gradient_color": "#FFFFFF",
            "water": "#C0C0C0",
            "parks": "#F0F0F0",
            "road_motorway": "#0A0A0A",
            "road_primary": "#1A1A1A",
            "road_secondary": "#2A2A2A",
            "road_tertiary": "#3A3A3A",
            "road_residential": "#4A4A4A",
            "road_default": "#3A3A3A",
            "ocean": "#D8F0FA"
        }

        if not os.path.exists(theme_file):
            return default_theme
        
        try:
            with open(theme_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading theme: {e}")
            return default_theme

    def get_coordinates(self, city, country):
        """Fetch coordinates with caching/retry logic.
        Returns (latitude, longitude) tuple.
        """
        location = self._geocode_location(city, country)
        return (location.latitude, location.longitude)

    def _geocode_location(self, city, country):
        """Internal geocode that returns the full Nominatim Location object."""
        geolocator = Nominatim(user_agent="city_map_poster_v2", timeout=10)
        # Address types that are too broad or too narrow for a city map
        TOO_BROAD = {'country', 'region'}
        TOO_NARROW = {'road', 'house', 'building', 'amenity', 'shop', 'tourism', 'highway'}
        try:
            # Structured queries enforce City-level matching (avoids streets like 'Dubai Bay')
            location = geolocator.geocode({'city': city, 'country': country}, addressdetails=True)

            if not location:
                location = geolocator.geocode({'town': city, 'country': country}, addressdetails=True)

            if not location:
                location = geolocator.geocode({'village': city, 'country': country}, addressdetails=True)

            # Check if we got a country/region-level fallback (too broad to map)
            # Allow state/province — Tokyo is a "province", Washington DC is a "state"
            if location:
                addr_type = location.raw.get('addresstype')
                if addr_type in TOO_BROAD:
                    location = None  # Discard, try free-form below

            # Free-form fallback: handles Tokyo, Beijing, and other cities that
            # Nominatim classifies above "city" level in structured queries.
            # First resolve the country to an ISO code so we can restrict results.
            if not location:
                country_code = None
                if country:
                    cc_lookup = geolocator.geocode({'country': country}, addressdetails=True)
                    if cc_lookup:
                        country_code = cc_lookup.raw.get('address', {}).get('country_code')

                location = geolocator.geocode(
                    f"{city}, {country}",
                    addressdetails=True,
                    country_codes=country_code,  # restrict to correct country
                )
                if location:
                    addr_type = location.raw.get('addresstype')
                    if addr_type in TOO_BROAD or addr_type in TOO_NARROW:
                        location = None  # Too broad or too specific (e.g. a road)

            if location:
                return location

            raise ValueError("Hmm — we couldn't find that location.\nTry checking the spelling, or make sure the city matches the country.")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Geocoding error: {str(e)}")

    def compute_auto_distance(self, city, country):
        """Compute an appropriate map distance (radius in meters) based on
        the Nominatim bounding box of the city.

        Returns (distance, lat, lon) where distance is clamped to [3000, 25000].
        """
        import math

        location = self._geocode_location(city, country)
        lat = location.latitude
        lon = location.longitude

        # Nominatim returns boundingbox as [south, north, west, east] strings
        bbox = location.raw.get('boundingbox')
        if not bbox or len(bbox) < 4:
            # No bbox available — fall back to a sensible default
            return (12000, lat, lon)

        south, north, west, east = [float(x) for x in bbox]

        # Haversine to compute diagonal span of the bounding box
        lat1, lat2 = math.radians(south), math.radians(north)
        lon1, lon2 = math.radians(west), math.radians(east)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        R = 6371000  # Earth radius in meters
        diagonal_m = R * c

        # Use ~40% of the diagonal as the radius — this frames the city well
        # without too much empty space or cropping
        auto_distance = diagonal_m * 0.4

        # Clamp to sane range
        auto_distance = max(3000, min(25000, auto_distance))

        # Round to nearest 500m for clean slider values
        auto_distance = round(auto_distance / 500) * 500

        print(f"Auto-distance for {city}, {country}: bbox diagonal={diagonal_m:.0f}m → distance={auto_distance}m")
        return (int(auto_distance), lat, lon)

    def _get_start_end_colors(self, color, location='bottom'):
        rgb = mcolors.to_rgb(color)
        vals = np.linspace(0, 1, 256).reshape(-1, 1)
        gradient = np.hstack((vals, vals))
        
        my_colors = np.zeros((256, 4))
        my_colors[:, 0:3] = rgb
        
        if location == 'bottom':
            my_colors[:, 3] = np.linspace(1, 0, 256)
            y_range_factor = (0, 0.25)
        else:
            my_colors[:, 3] = np.linspace(0, 1, 256)
            y_range_factor = (0.75, 1.0)
            
        custom_cmap = mcolors.ListedColormap(my_colors)
        return gradient, custom_cmap, y_range_factor

    def _create_gradient_fade(self, ax, color, location='bottom', zorder=10):
        gradient, custom_cmap, (start_fac, end_fac) = self._get_start_end_colors(color, location)
        
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        y_range = ylim[1] - ylim[0]
        
        y_bottom = ylim[0] + y_range * start_fac
        y_top = ylim[0] + y_range * end_fac
        
        ax.imshow(gradient, extent=[xlim[0], xlim[1], y_bottom, y_top], 
                  aspect='auto', cmap=custom_cmap, zorder=zorder, origin='lower')

    def _get_road_style(self, G, theme):
        colors = []
        widths = []
        
        is_gdf = isinstance(G, gpd.GeoDataFrame)
        edges = G.itertuples() if is_gdf else G.edges(data=True)
        
        for item in edges:
            if is_gdf:
                highway = getattr(item, 'highway', 'unclassified')
            else:
                data = item[2]
                highway = data.get('highway', 'unclassified')
                
            if isinstance(highway, list):
                highway = highway[0] if highway else 'unclassified'
            
            if highway in ['motorway', 'motorway_link']:
                colors.append(theme['road_motorway'])
                widths.append(1.2)
            elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']:
                colors.append(theme['road_primary'])
                widths.append(1.0)
            elif highway in ['secondary', 'secondary_link']:
                colors.append(theme['road_secondary'])
                widths.append(0.8)
            elif highway in ['tertiary', 'tertiary_link']:
                colors.append(theme['road_tertiary'])
                widths.append(0.6)
            else:
                colors.append(theme['road_residential'])
                widths.append(0.4)
                
        return colors, widths

    def _fetch_map_data(self, point, distance, visibility=None, callback=None, use_disk_cache=True, city=None, country=None):
        """Fetch all map data required for a poster or preview.
           Sequential execution for better progress tracking.
        """
        # 1. Check Cache (only if caching is enabled)
        # FULL FETCH OPTIMIZATION: Cache key no longer depends on visibility.
        # It only depends on location and fetch distance.
        cache_key = (point, distance, "full_fetch_v8")
        
        if use_disk_cache:
            # Check in-memory cache first (fastest)
            if cache_key in self.data_cache:
                if callback: callback("Using cached data...", 100)
                print("Memory cache hit! Returning pre-fetched data.")
                self.data_cache.move_to_end(cache_key)  # Mark as recently used
                return self.data_cache[cache_key]
            
            # Check disk cache
            disk_data = self._load_cache_from_disk(cache_key)
            if disk_data is not None:
                if callback: callback("Using cached data...", 100)
                # Store in memory cache for even faster subsequent access
                self.data_cache[cache_key] = disk_data
                return disk_data

        if callback: callback("Initializing download...", 5)
        
        # 2. GIS SPATIAL CACHE (PostGIS)
        # Instead of strict exact cache keys, we check if PostGIS has the data for our radius
        if use_disk_cache and self.geo_store and hasattr(self.geo_store, 'load'):
            try:
                gdf_roads, gdf_water, gdf_parks, gdf_ocean = self.geo_store.load(point[1], point[0], distance)
                if gdf_roads is not None and not gdf_roads.empty:
                    if callback: callback("Loaded optimized spatial data from GIS...", 100)
                    print("PostGIS Spatial Cache hit! Bypassing Overpass completely.")
                    
                    # Store in memory cache for even faster subsequent access
                    result = (gdf_roads, gdf_water, gdf_parks, gdf_ocean)
                    self.data_cache[cache_key] = result
                    return result
            except Exception as e:
                print(f"Warning: PostGIS load failed, falling back to Overpass: {e}")

        print("Downloading map data...")
        
        # Default visibility (everything on)
        if visibility is None:
            visibility = {
                'water': True, 'parks': True, 
                'road_motorway': True, 'road_primary': True, 
                'road_secondary': True, 'road_tertiary': True, 
                'road_residential': True
            }

        # --- PARALLEL FETCH EXECUTION ---
        # We define helper functions to run in threads so we can maintain the detailed logic
        # while gaining parallel speed.

        def fetch_roads():
            try:
                requested_road_types = [
                    "motorway", "motorway_link",
                    "trunk", "trunk_link", "primary", "primary_link",
                    "secondary", "secondary_link",
                    "tertiary", "tertiary_link",
                ]

                # Tiered road inclusion based on zoom level (distance = fetch_distance = user × 1.5)
                # More road types at closer zoom, fewer at wider zoom to prevent OOM
                if distance <= 6000:
                    # Very close zoom (user distance ≤ 4000): everything including service roads & paths
                    requested_road_types.extend([
                        "residential", "unclassified", "living_street",
                        "service", "pedestrian", "track",
                    ])
                    print(f"Fetching ALL road types including service/pedestrian (distance={distance})...")
                elif distance <= 12000:
                    # Medium zoom (user distance ≤ 8000): residential + service roads
                    requested_road_types.extend([
                        "residential", "unclassified", "living_street",
                        "service",
                    ])
                    print(f"Fetching roads including residential+service (distance={distance})...")
                elif distance <= 18000:
                    # Medium-wide zoom (user distance ≤ 12000): residential only
                    requested_road_types.extend(["residential", "unclassified", "living_street"])
                    print(f"Fetching roads including residential (distance={distance})...")
                else:
                    print(f"Fetching major roads only (distance={distance}, residential skipped)...")

                highway_regex = "|".join(requested_road_types)
                custom_filter = f'["highway"~"{highway_regex}"]'
                return ox.graph_from_point(point, dist=distance, dist_type='bbox', custom_filter=custom_filter)
            except Exception as e:
                print(f"Error fetching roads: {e}")
                return None

        def fetch_hydrology():
            try:
                print("Fetching water features for cache...")
                hydro_tags = {
                    'natural': ['water'],
                    'waterway': ['riverbank', 'dock'],
                    'landuse': ['reservoir']
                }
                # Use bbox query instead of point query so large water bodies
                # (e.g. St. Lawrence River) whose nodes fall outside the radius
                # are still captured if they intersect the map area.
                import math
                lat, lon = point
                cos_lat = math.cos(math.radians(lat))
                height_deg = (distance * 2.0) / 111320.0
                width_deg = height_deg / cos_lat
                bbox = (lon - width_deg / 2, lat - height_deg / 2,
                        lon + width_deg / 2, lat + height_deg / 2)
                gdf = ox.features_from_bbox(bbox, tags=hydro_tags)
                return gdf
            except Exception as e:
                print(f"Error fetching hydro: {e}")
                return None

        def fetch_parks():
            try:
                print("Fetching ALL parks for cache...")
                park_tags = {
                    'leisure': ['park', 'nature_reserve', 'golf_course', 'garden', 'pitch'],
                    'landuse': ['grass', 'forest', 'meadow', 'recreation_ground', 'village_green', 'allotments', 'orchard'],
                    'natural': ['wood', 'scrub', 'heath', 'grassland']
                }
                # Use bbox query (like hydrology) so large parks whose centroid
                # falls outside the radius are still captured.
                import math
                lat, lon = point
                cos_lat = math.cos(math.radians(lat))
                height_deg = (distance * 2.0) / 111320.0
                width_deg = height_deg / cos_lat
                bbox = (lon - width_deg / 2, lat - height_deg / 2,
                        lon + width_deg / 2, lat + height_deg / 2)
                return ox.features_from_bbox(bbox, tags=park_tags)
            except Exception as e:
                print(f"Error fetching parks: {e}")
                return None

        # Execute in ThreadPool with per-layer progress updates
        if callback: callback("Downloading map layers in parallel...", 15)

        G_full = None
        water = None
        ocean = None
        parks = None

        def fetch_ocean():
            return self._get_ocean_for_bbox(point, distance)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fetch_roads): 'Roads',
                executor.submit(fetch_hydrology): 'Water',
                executor.submit(fetch_parks): 'Parks',
                executor.submit(fetch_ocean): 'Ocean',
            }

            results = {}
            done = 0
            for future in as_completed(futures):
                layer_name = futures[future]
                results[layer_name] = future.result()
                done += 1
                if callback:
                    callback(f"Downloaded {layer_name} ({done}/4)...", 15 + done * 12)

            G_full = results.get('Roads')
            water = results.get('Water')
            parks = results.get('Parks')
            ocean = results.get('Ocean')

        # Subtract ocean from parks so forests/parks don't bleed into water.
        # OSM forest/park polygons often have boundaries that extend past the
        # actual coastline (e.g. Pacific Spirit Park in Vancouver).
        # Optimized: only apply difference() to parks that actually intersect ocean.
        if parks is not None and not parks.empty and ocean is not None and not ocean.empty:
            try:
                from shapely.ops import unary_union
                ocean_union = unary_union(ocean.geometry)
                parks = parks.copy()
                # Pre-filter: only polygons that intersect ocean need subtraction
                is_poly = parks.geometry.apply(lambda g: g.geom_type in ('Polygon', 'MultiPolygon') and not g.is_empty)
                touches_ocean = parks.geometry.intersects(ocean_union)
                needs_fix = is_poly & touches_ocean
                if needs_fix.any():
                    parks.loc[needs_fix, 'geometry'] = parks.loc[needs_fix, 'geometry'].apply(
                        lambda g: g.difference(ocean_union)
                    )
                parks = parks[~parks.geometry.is_empty]
                print(f"Subtracted ocean from {needs_fix.sum()} parks ({len(parks)} remaining)")
            except Exception as e:
                print(f"Warning: Failed to subtract ocean from parks: {e}")

        # Post-processing: skip isolate removal — isolated nodes are harmless
        # (they don't appear in graph_to_gdfs edges) and removal is expensive (O(V+E))
        G = G_full
        if G is not None:
            if callback: callback("Processing layers...", 75)
            
        result = (G, water, parks, ocean)

        # ALWAYS save to cache (both cloud and local) after fetching fresh data
        # This ensures "Fresh Mode" still populates the cache for next time
        # Save to Disk/Cloud Cache (Level 1)
        self._save_cache_to_disk(cache_key, result)
        # Store in memory cache for faster subsequent access
        self.data_cache[cache_key] = result

        # Best-effort: persist real geometries to PostGIS (background, non-blocking)
        if self.geo_store:
            cache_hash = self._get_cache_key_hash(cache_key)
            self._upload_executor.submit(self._save_geo_to_postgis, city, country, cache_hash, water, parks, ocean, G)

        # Force garbage collection to free intermediate OSM/Overpass objects
        gc.collect()

        return result

    def _generate_preview_json(self, city, country, point, G, water, parks, ocean=None, format_name="poster_vertical", distance=12000, callback=None):
        """Internal method to generate the preview JSON structure."""
        
        fmt = self.MAP_FORMATS.get(format_name, self.MAP_FORMATS['poster_vertical'])
        view_width = fmt['view_width']
        view_height = fmt['view_height']

        # Determine scale based on PROJECTED dimensions to fix distortion
        import math
        center_lat_rad = math.radians(point[0])
        cos_lat = math.cos(center_lat_rad)
        
        # Calculate fixed bounding box based on distance (radius) to ensure constant zoom
        # A 12000m radius means the map covers approx 24000m width/height (depending on aspect ratio)
        # We want the 'distance' to roughly correspond to the smaller dimension of the view
        
        # distance is "radius", so full span is 2 * distance
        span_meters = distance * 2.0 
        
        # Convert meters to degrees (approx)
        # 1 degree lat = 111,320 meters
        degrees_height = span_meters / 111320.0
        degrees_width = degrees_height / cos_lat
        
        # Determine strict bounds based on format aspect ratio
        # The 'distance' defines the minimum coverage (e.g. ensuring at least radius X is visible)
        aspect_ratio = view_width / view_height
        
        if aspect_ratio > 1:
            # Landscape: Height is constrained (Distance = Height)
            height_meters = span_meters
            width_meters = span_meters * aspect_ratio
        else:
            # Portrait: Width is constrained (Distance = Width)
            width_meters = span_meters
            height_meters = span_meters / aspect_ratio
            
        # Convert meters to degrees
        target_height_deg = height_meters / 111320.0
        target_width_deg = width_meters / (111320.0 * cos_lat)

        # Determine scaling factors
        # 1 radian longitude = 111320 * cos(lat) meters
        # We want to map 'target_width_deg' to 'view_width'
        
        # Projection factor: how many pixels per degree of longitude?
        # px = (lon - center) * (pixels / degree_lon)
        # pixels / degree_lon = (view_width / target_width_deg) * cos_lat 
        # Wait, my transform function handles projection. I just need "pixels per degree".
        
        # final_scale represents "pixels per degree" (roughly)
        
        scale_x = view_width / (target_width_deg * cos_lat)
        scale_y = view_height / target_height_deg
        
        final_scale = min(scale_x, scale_y) # Should be identical by definition above
        
        # Center points in projected space
        # We use the REQUESTED point as the center, not the data center
        center_x_deg = point[1]
        center_y_deg = point[0]

        # Pre-compute constants for vectorized transforms
        half_w = view_width / 2
        half_h = view_height / 2
        cx = center_x_deg
        cy = center_y_deg
        scale_x = cos_lat * final_scale
        scale_y = final_scale

        def _coords_to_svg(coords_array, close=False):
            """Batch-convert coordinate array to SVG path string using NumPy."""
            px = np.round(half_w + (coords_array[:, 0] - cx) * scale_x, 1)
            py = np.round(half_h - (coords_array[:, 1] - cy) * scale_y, 1)
            # Convert to string arrays and concatenate — avoids per-element Python formatting
            px_str = px.astype(str)
            py_str = py.astype(str)
            # Build "L x y" for all points, then fix first to "M x y"
            commands = np.char.add(np.char.add("L ", px_str), np.char.add(" ", py_str))
            commands[0] = f"M {px_str[0]} {py_str[0]}"
            result = " ".join(commands)
            return result + " Z" if close else result

        def to_svg_path(geometry):
            """Convert geometry to SVG path using vectorized NumPy transforms."""
            if geometry is None or geometry.is_empty:
                return ""

            if geometry.geom_type == 'Polygon':
                # Exterior ring + interior rings (holes/islands)
                parts = [_coords_to_svg(np.array(geometry.exterior.coords), close=True)]
                for interior in geometry.interiors:
                    parts.append(_coords_to_svg(np.array(interior.coords), close=True))
                return " ".join(parts)

            elif geometry.geom_type == 'LineString':
                return _coords_to_svg(np.array(geometry.coords), close=False)

            elif geometry.geom_type == 'MultiPolygon':
                return " ".join(to_svg_path(poly) for poly in geometry.geoms)

            elif geometry.geom_type == 'MultiLineString':
                return " ".join(
                    _coords_to_svg(np.array(line.coords), close=False)
                    for line in geometry.geoms
                )

            elif geometry.geom_type == 'GeometryCollection':
                return " ".join(
                    to_svg_path(geom) for geom in geometry.geoms
                    if geom is not None and not geom.is_empty
                )

            return ""

        # Format coordinates like the poster
        lat, lon = point
        coords_str = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
        if lon < 0:
            coords_str = coords_str.replace("E", "W")

        # Process layers
        preview_data = {
            "viewBox": f"0 0 {view_width} {view_height}",
            "water": [],
            "ocean": [],
            "parks": [],
            "roads": {
                "motorway": [],
                "primary": [],
                "secondary": [],
                "tertiary": [],
                "residential": []
            },
            "info": {
                "city": city,
                "spaced_city": "  ".join(list(city.upper())),
                "country": country.upper(),
                "coordinates": coords_str,
                "lat": lat,
                "lon": lon
            }
        }
        
        # Helper to emit progress updates (no deepcopy — just send progress info)
        def emit_partial(msg, pct):
            if callback:
                callback(msg, pct)

        # Clip box in lat/lon — used to trim large polygons (e.g. rivers, ocean)
        # to the visible viewport so we don't send 100s of KB of off-screen path data.
        from shapely.geometry import box as shapely_box
        clip_box = shapely_box(
            cx - target_width_deg / 2 * 1.1,   # slight buffer so edges aren't clipped visibly
            cy - target_height_deg / 2 * 1.1,
            cx + target_width_deg / 2 * 1.1,
            cy + target_height_deg / 2 * 1.1
        )

        def clip_and_convert(geom):
            """Clip geometry to viewport bbox, then convert to SVG path."""
            if geom is None or geom.is_empty:
                return ""
            try:
                clipped = geom.intersection(clip_box)
                if clipped.is_empty:
                    return ""
                return to_svg_path(clipped)
            except Exception:
                return to_svg_path(geom)  # fallback: unclipped

        if ocean is not None and not ocean.empty:
            seen = set()
            for geom in ocean.geometry:
                if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue
                path = clip_and_convert(geom)
                if path and path not in seen:
                    seen.add(path)
                    preview_data["ocean"].append(path)
            emit_partial("Rendering ocean...", 82)

        if water is not None and not water.empty:
            seen = set()
            for geom in water.geometry:
                if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue
                path = clip_and_convert(geom)
                if path and path not in seen:
                    seen.add(path)
                    preview_data["water"].append(path)
            emit_partial("Rendering water...", 85)

        if parks is not None and not parks.empty:
            seen = set()
            for geom in parks.geometry:
                if geom.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue
                path = clip_and_convert(geom)
                if path and path not in seen:
                    seen.add(path)
                    preview_data["parks"].append(path)
            emit_partial("Rendering parks...", 88)

        # VECTORIZED ROAD PROCESSING
        # Instead of iterating 50k edges in python loop, use GeoPandas group-by
        if G is not None:
            is_gdf = isinstance(G, gpd.GeoDataFrame)
            has_edges = not G.empty if is_gdf else len(G.edges) > 0
            
            if has_edges:
                try:
                    if is_gdf:
                        gdf_edges = G.copy()
                    else:
                        # Ensure CRS attribute exists (missing in some OSMnx versions/cache formats)
                        if not hasattr(G.graph, 'get') or 'crs' not in G.graph:
                            G.graph['crs'] = 'EPSG:4326'
                        # Convert graph to GDF once - this is fast
                        gdf_edges = ox.graph_to_gdfs(G, nodes=False)

                    # Normalize 'highway' column: explode lists if necessary or take first
                    # Actually, ox usually returns lists for highway if multiple types.
                    # We need a single string for grouping.

                    def get_first_highway(val):
                         if isinstance(val, list): return val[0]
                         return val

                    gdf_edges['highway_single'] = gdf_edges['highway'].apply(get_first_highway)

                    # Pre-calculate paths
                    # Using apply is faster than iterating rows manually
                    # We can also check geometry validity
                    gdf_edges = gdf_edges[gdf_edges.geometry.notnull() & ~gdf_edges.geometry.is_empty]
                    gdf_edges['svg_path'] = gdf_edges.geometry.apply(to_svg_path)

                    # Group by highway type
                    grouped = gdf_edges.groupby('highway_single')

                    # Mapping of highway types to our categories
                    cat_map = {
                        'motorway': 'motorway', 'motorway_link': 'motorway',
                        'trunk': 'primary', 'trunk_link': 'primary', 'primary': 'primary', 'primary_link': 'primary',
                        'secondary': 'secondary', 'secondary_link': 'secondary',
                        'tertiary': 'tertiary', 'tertiary_link': 'tertiary'
                    }
                    # everything else is 'residential'

                    road_progress = 90
                    for highway_type, group in grouped:
                        category = cat_map.get(highway_type, 'residential')
                        # If highway_type was not in our map (e.g. unclassified, service), it goes to residential

                        # Add all paths for this group
                        paths = group['svg_path'].tolist()
                        # Filter out empty strings if any
                        paths = [p for p in paths if p]

                        preview_data["roads"][category].extend(paths)

                        # Emit partial update for each road category
                        road_progress = min(road_progress + 2, 98)
                        emit_partial(f"Rendering {category} roads...", road_progress)

                except Exception as e:
                    print(f"Error optimizing roads: {e}. Fallback to iteration.")
                    # Fallback if GDF conversion fails (rare)
                    pass

        return preview_data

    def get_preview_data(self, city, country, distance=12000, visibility=None, format_name="poster_vertical", callback=None, use_cache=True, theme_name=None, custom_colors=None):
        """Generate lightweight SVG path data for interactive preview."""
        
        # --- LEVEL 2 CACHE: JSON Output ---
        # Check if we have the final JSON already cached. This bypasses geometry processing.
        json_cache_key = (city, country, distance, tuple(sorted(visibility.items())) if visibility else None, format_name, "json_v7")
        
        if use_cache:
            json_data = self._load_cache_from_disk(json_cache_key)
            if json_data:
                if callback: callback("Loaded preview from cache!", 100)
                print("JSON Cache Hit! Returning pre-rendered preview.")
                
                # Ensure history SVG is saved/updated even on cache hit
                if theme_name:
                     self._save_preview_history(city, country, distance, visibility, format_name, theme_name, custom_colors, json_data)
                
                return json_data

        if callback: callback("📍 locating city...", 5)
        point = self.get_coordinates(city, country)
        
        # IMPORTANT: Use a FIXED fetch distance multiplier regardless of format
        # This ensures we hit the same Level 1 cache when switching formats.
        # 2.0x covers all aspect ratios: the most extreme is 16:9 (desktop)
        # which needs ~1.78x the distance in width, so 2.0x provides headroom.
        fetch_distance = distance * 2.0

        G, water, parks, ocean = self._fetch_map_data(point, fetch_distance, visibility, callback, use_disk_cache=use_cache, city=city, country=country)

        if callback: callback("Generating preview geometry...", 80)
        
        # Handle case where no streets are fetched (G is None)
        if G is None:
            import math
            G = nx.MultiDiGraph()
            print("Created dummy graph (no streets found)")

        result_json = self._generate_preview_json(city, country, point, G, water, parks, ocean, format_name, distance, callback)
        
        # Always save to Level 2 Cache (even when use_cache=false, to overwrite stale data)
        self._save_cache_to_disk(json_cache_key, result_json)
            
        # Save to History (if theme provided)
        if theme_name:
             self._save_preview_history(city, country, distance, visibility, format_name, theme_name, custom_colors, result_json)

        return result_json

    def _xml_escape(self, text):
        """Escape XML special characters to prevent SVG injection."""
        if not text:
            return ""
        return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))

    def _save_preview_history(self, city, country, distance, visibility, format_name, theme_name, custom_colors, preview_json):
        """Save preview metadata and generate an SVG thumbnail for history."""
        try:
            # 1. Sanitize filename
            safe_city = "".join([c for c in city if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            base_filename = f"preview_{safe_city.replace(' ', '_')}"
            
            # 2. Save Metadata
            metadata = {
                "city": city,
                "country": country,
                "distance": distance,
                "theme": theme_name,
                "custom_colors": custom_colors,
                "layer_visibility": visibility,
                "format": format_name,
                "type": "preview",
                "timestamp": time.time()
            }
            
            meta_path = os.path.join(self.posters_dir, f"{base_filename}.json")
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            print(f"Saved preview metadata: {base_filename}.json")

            # 3. Generate SVG Thumbnail
            # Colors: blend theme defaults with custom overrides
            theme_defaults = self.load_theme(theme_name)
            colors = theme_defaults.copy()
            if custom_colors:
                colors.update(custom_colors)
                
            # SVG Header
            view_box = preview_json['viewBox']
            svg_content = [
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" style="background-color: {colors.get("bg", "#000")}">'
            ]
            
            # Polygons (Water/Parks)
            # Simplified: just dump paths. Note: Preview JSON separates them by type.
            
            # Helper to add paths
            def add_layer(layer_name, color_key, fallback_color):
                paths = preview_json.get(layer_name, [])
                color = colors.get(color_key, fallback_color)
                if paths:
                    # Combine all paths into one <path> for file size efficiency if possible, 
                    # but they are list of strings. Let's just iterate.
                    full_path_d = " ".join(paths)
                    svg_content.append(f'<path d="{full_path_d}" fill="{color}" fill-rule="evenodd" stroke="none" />')

            # Add Ocean/Water/Parks
            # In preview_json, ocean is separate? let's check structure.
            # _generate_preview_json returns: { roads: {...}, water: [...], parks: [...], ocean: [...], viewBox: ... }
            
            add_layer("ocean", "ocean", "#D8F0FA")
            add_layer("water", "water", "#1A1A1A")
            add_layer("parks", "parks", "#202020")
            
            # Roads (Lines)
            road_widths = {
                'motorway': 4, 'trunk': 4, 'primary': 3,
                'secondary': 2, 'tertiary': 1.5, 'residential': 1
            }
            

            roads = preview_json.get('roads', {})
            # Draw in order: residential -> tertiary -> secondary -> primary -> motor
            order = ['residential', 'tertiary', 'secondary', 'primary', 'trunk', 'motorway']
            
            for r_type in order:
                paths = roads.get(r_type, [])
                if not paths: continue
                # Handle mapped types (e.g. trunk -> road_primary key in colors)
                color_key = f"road_{r_type}" if r_type in ['motorway', 'residential'] else f"road_{r_type}"
                if r_type in ['trunk', 'primary']: color_key = 'road_primary'
                if r_type in ['secondary']: color_key = 'road_secondary'
                if r_type in ['tertiary']: color_key = 'road_tertiary'
                
                color = colors.get(color_key, "#fff")
                width = road_widths.get(r_type, 1)
                
                full_d = " ".join(paths)
                svg_content.append(f'<path d="{full_d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" />')

            # Add Text Overlay defined in preview_json or just use passed args
            # We need to parse viewBox to know where to put text
            try:
                vb_parts = view_box.split()
                vb_w = float(vb_parts[2])
                vb_h = float(vb_parts[3])
                
                text_color = colors.get('text', '#cccccc')
                
                # Center X
                cx = vb_w / 2
                
                # Bottom padding
                pad_bottom = vb_h * 0.05
                
                # Font sizes adjusted for typical 1000px width
                fs_city = vb_w * 0.08  # ~80px
                fs_country = vb_w * 0.04 # ~40px
                fs_coords = vb_w * 0.025 # ~25px
                
                # Y positions
                y_city = vb_h - (vb_h * 0.15)
                y_country = y_city + fs_country + 10
                y_coords = y_country + fs_coords + 15
                
                # City (Spaced) - with dynamic sizing for long names
                city_text = "  ".join(list(city.upper()))
                char_count = len(city.replace(" ", ""))
                city_font_size = fs_city * max(0.5, 10 / char_count) if char_count > 10 else fs_city
                safe_city_text = self._xml_escape(city_text)
                svg_content.append(f'<text x="{cx}" y="{y_city}" fill="{text_color}" font-family="sans-serif" font-weight="bold" font-size="{city_font_size}" text-anchor="middle" letter-spacing="4">{safe_city_text}</text>')
                
                # Country
                safe_country = self._xml_escape(country.upper())
                svg_content.append(f'<text x="{cx}" y="{y_country}" fill="{text_color}" font-family="sans-serif" font-size="{fs_country}" text-anchor="middle" letter-spacing="2">{safe_country}</text>')
                
                # Coordinates
                # We can grab pre-formatted string from preview_json info if available, or reconstruct
                info = preview_json.get('info', {})
                coords_str = info.get('coordinates', '')
                if not coords_str:
                     # Fallback
                    lat, lon = info.get('lat', 0), info.get('lon', 0)
                    coords_str = f"{lat:.4f}° N / {lon:.4f}° E"
                
                safe_coords = self._xml_escape(coords_str)
                svg_content.append(f'<text x="{cx}" y="{y_coords}" fill="{text_color}" font-family="sans-serif" font-size="{fs_coords}" text-anchor="middle" letter-spacing="1">{safe_coords}</text>')

            except Exception as e:
                print(f"Error adding text to SVG thumbnail: {e}")
                
            svg_content.append('</svg>')
            
            svg_path = os.path.join(self.posters_dir, f"{base_filename}.svg")
            with open(svg_path, 'w') as f:
                f.write("\n".join(svg_content))
                
            print(f"Saved preview SVG: {base_filename}.svg")

            # Record durable history (e.g. Postgres) if a hook is configured
            if self.history_hook:
                try:
                    self.history_hook({**metadata, "filename": f"{base_filename}.svg"})
                except Exception as hook_e:
                    print(f"Warning: History hook failed: {hook_e}")

        except Exception as e:
            print(f"Warning: Failed to save preview history: {e}")

    def generate_poster(self, city, country, theme_name="feature_based", distance=29000, custom_colors=None, visibility=None, format_name="poster_vertical", callback=None, use_cache=True, lat=None, lon=None):
        """Main generation function."""
        # Force cache usage for high-res generation as per user request.
        # Rationale: The user likely just generated a preview (which might have fetched fresh data).
        # We want to reuse that exact data for the poster to ensure consistency and speed.
        use_cache = True

        # Build deterministic filename from inputs so repeated clicks don't re-render
        poster_key = f"{lat}|{lon}|{city}|{country}|{theme_name}|{distance}|{format_name}|{json.dumps(custom_colors, sort_keys=True) if custom_colors else ''}|{json.dumps(visibility, sort_keys=True) if visibility else ''}"
        poster_hash = hashlib.md5(poster_key.encode()).hexdigest()[:12]
        safe_city = city.lower().replace(' ', '_')
        filename = f"{safe_city}_{theme_name}_{poster_hash}.png"
        output_path = os.path.join(self.posters_dir, filename)

        # Check if this exact poster already exists on disk
        if os.path.exists(output_path):
            if callback: callback("Poster already generated!", 100)
            print(f"Poster cache hit: {filename}")
            return output_path

        # Load theme
        theme = self.load_theme(theme_name)

        # Apply custom overrides if provided
        if custom_colors:
            print("Applying custom color overrides...")
            theme.update(custom_colors)

        # Get coordinates
        if lat is not None and lon is not None:
            point = (lat, lon)
        else:
            if callback: callback(f"Locating {city}...", 5)
            print(f"Fetching coordinates for {city}, {country}...")
            point = self.get_coordinates(city, country)
        
        # IMPORTANT: Use a FIXED fetch distance multiplier regardless of format
        # This ensures we hit the same Level 1 cache when switching formats.
        # 2.0x covers all aspect ratios: the most extreme is 16:9 (desktop)
        # which needs ~1.78x the distance in width, so 2.0x provides headroom.
        fetch_distance = distance * 2.0

        # Fetch data
        G, water, parks, ocean = self._fetch_map_data(point, fetch_distance, visibility, callback, use_disk_cache=use_cache, city=city, country=country)

        # Create plot
        if callback: callback("Rendering high-res map...", 70)
        print("Rendering map...")
        
        fmt = self.MAP_FORMATS.get(format_name, self.MAP_FORMATS['poster_vertical'])
        # DPI setting logic could vary, but using config
        dpi = fmt.get('dpi', 300)
        
        fig, ax = plt.subplots(figsize=(fmt['width'], fmt['height']), facecolor=theme['bg'])
        ax.set_facecolor(theme['bg'])
        ax.set_position([0, 0, 1, 1])
        
        # Plot layers (filter out Point geometries to avoid orange dots)
        # Respect visibility toggles so PNG matches SVG preview
        if (visibility is None or visibility.get('ocean', True)) and ocean is not None and not ocean.empty:
            ocean_color = theme.get('ocean', '#a2bff2')
            # Filter to only Polygon and MultiPolygon geometries
            ocean_filtered = ocean[ocean.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            if not ocean_filtered.empty:
                ocean_filtered.plot(ax=ax, facecolor=ocean_color, edgecolor='none', zorder=0.5)

        if (visibility is None or visibility.get('water', True)) and water is not None and not water.empty:
            # Filter to only Polygon and MultiPolygon geometries
            water_filtered = water[water.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            if not water_filtered.empty:
                water_filtered.plot(ax=ax, facecolor=theme['water'], edgecolor='none', zorder=1)

        if (visibility is None or visibility.get('parks', True)) and parks is not None and not parks.empty:
            # Filter to only Polygon and MultiPolygon geometries
            parks_filtered = parks[parks.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            if not parks_filtered.empty:
                parks_filtered.plot(ax=ax, facecolor=theme['parks'], edgecolor='none', zorder=2)
            
        edge_colors, edge_widths = self._get_road_style(G, theme)

        # Manual edge plotting to avoid node rendering issues
        # Respects visibility toggles so PNG matches SVG preview
        from matplotlib.collections import LineCollection

        if G is not None:
            is_gdf = isinstance(G, gpd.GeoDataFrame)
            has_edges = not G.empty if is_gdf else len(G.edges) > 0
            
            if has_edges:
                visible_lines = []
                visible_colors = []
                visible_widths = []

                edges_iter = enumerate(G.itertuples()) if is_gdf else enumerate(G.edges(data=True))

                for i, item in edges_iter:
                    # Determine road category for visibility check
                    if is_gdf:
                        highway = getattr(item, 'highway', 'unclassified')
                        geom = getattr(item, 'geometry', None)
                    else:
                        u, v, data = item[1]
                        highway = data.get('highway', 'unclassified')
                        geom = data.get('geometry')
                        
                    if visibility:
                        if isinstance(highway, list):
                            highway = highway[0] if highway else 'unclassified'

                        if highway in ['motorway', 'motorway_link']:
                            category = 'road_motorway'
                        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']:
                            category = 'road_primary'
                        elif highway in ['secondary', 'secondary_link']:
                            category = 'road_secondary'
                        elif highway in ['tertiary', 'tertiary_link']:
                            category = 'road_tertiary'
                        else:
                            category = 'road_residential'

                        # Skip if this road category is toggled off
                        if visibility.get(category) is False:
                            continue

                    # Get edge geometry
                    if geom is not None and not geom.is_empty:
                        # Handle MultiLineString vs LineString
                        if geom.geom_type == 'MultiLineString':
                            for line in geom.geoms:
                                xs, ys = line.xy
                                visible_lines.append(list(zip(xs, ys)))
                                visible_colors.append(edge_colors[i])
                                visible_widths.append(edge_widths[i])
                            continue
                        else:
                            xs, ys = geom.xy
                            visible_lines.append(list(zip(xs, ys)))
                    elif not is_gdf:
                        x = [G.nodes[u]['x'], G.nodes[v]['x']]
                        y = [G.nodes[u]['y'], G.nodes[v]['y']]
                        visible_lines.append(list(zip(x, y)))
                        
                    visible_colors.append(edge_colors[i])
                    visible_widths.append(edge_widths[i])

                if visible_lines:
                    lc = LineCollection(visible_lines, colors=visible_colors, linewidths=visible_widths,
                                      capstyle='butt', joinstyle='round', zorder=3)
                    ax.add_collection(lc)

        # Enforce exact bounds to match preview (and distance)
        # Calculate theoretical bounds based on distance and aspect ratio
        import math
        center_lat, center_lon = point
        center_lat_rad = math.radians(center_lat)
        cos_lat = math.cos(center_lat_rad)
        
        # Full span in meters (diameter)
        span_meters = distance * 2.0 
        
        # Convert to degrees
        degrees_height = span_meters / 111320.0
        degrees_width = degrees_height / cos_lat
        
        # Adjust for Aspect Ratio
        aspect_ratio = fmt['width'] / fmt['height']
        
        if aspect_ratio > 1:
            # Landscape: Height is constrained (Distance = Height)
            # span_meters covers height
            height_meters = span_meters
            width_meters = span_meters * aspect_ratio
        else:
            # Portrait: Width is constrained (Distance = Width)
            # span_meters covers width
            width_meters = span_meters
            height_meters = span_meters / aspect_ratio
            
        # Convert meters to degrees
        target_height_deg = height_meters / 111320.0
        target_width_deg = width_meters / (111320.0 * cos_lat)
            
        # Set explicit limits centered on the point
        min_x = center_lon - (target_width_deg / 2)
        max_x = center_lon + (target_width_deg / 2)
        min_y = center_lat - (target_height_deg / 2)
        max_y = center_lat + (target_height_deg / 2)
        
        ax.set_xlim(min_x, max_x)
        ax.set_ylim(min_y, max_y)
        
        # CORRECT ASPECT RATIO to avoid squishing
        # We plot in degrees, but we want it visually correct (Mercator-ish)
        # Ratio of y-unit (deg lat) to x-unit (deg lon) should be 1 / cos(lat)
        ax.set_aspect(1.0 / cos_lat)
        
        # Gradients
        self._create_gradient_fade(ax, theme['gradient_color'], 'bottom')
        self._create_gradient_fade(ax, theme['gradient_color'], 'top')
        
        # Typography
        self._add_typography(ax, city, country, point, theme)
        
        # Save (filename already determined above via content hash)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if callback: callback("Saving final image...", 90)
        print(f"Saving to {output_path}...")
        plt.savefig(output_path, dpi=dpi, facecolor=theme['bg'])
        plt.close()
        
        # Save metadata
        metadata = {
            "city": city,
            "country": country,
            "theme": theme_name,
            "format": format_name,
            "distance": distance,
            "custom_colors": custom_colors,
            "timestamp": timestamp,
            "filename": filename
        }
        json_path = output_path.replace('.png', '.json')
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save preview data for Instant Restore
        try:
           preview_json = self._generate_preview_json(city, country, point, G, water, parks, ocean, format_name)
           preview_path = output_path.replace('.png', '.preview.json')
           with open(preview_path, 'w') as f:
               json.dump(preview_json, f) 
        except Exception as e:
           print(f"Warning: Failed to save preview cache: {e}")

        # Record durable history (e.g. Postgres) if a hook is configured
        if self.history_hook:
            try:
                if callback: callback("Saving history...", 95)
                self.history_hook(metadata)
            except Exception as hook_e:
                print(f"Warning: History hook failed: {hook_e}")

        return output_path

    def _add_typography(self, ax, city, country, point, theme):
        if self.fonts:
            font_main = FontProperties(fname=self.fonts['bold'], size=60)
            font_top = FontProperties(fname=self.fonts['bold'], size=40)
            font_sub = FontProperties(fname=self.fonts['light'], size=22)
            font_coords = FontProperties(fname=self.fonts['regular'], size=14)
            font_attr = FontProperties(fname=self.fonts['light'], size=8)
        else:
            font_main = FontProperties(family='monospace', weight='bold', size=60)
            font_top = FontProperties(family='monospace', weight='bold', size=40)
            font_sub = FontProperties(family='monospace', weight='normal', size=22)
            font_coords = FontProperties(family='monospace', size=14)
            font_attr = FontProperties(family='monospace', size=8)

        spaced_city = "  ".join(list(city.upper()))

        # Determine accent color
        accent_color = theme.get('accent', theme['text'])

        # Dynamic font sizing for long city names
        # Scale down font for longer names to prevent overflow
        char_count = len(city.replace(" ", ""))
        if char_count > 10:
            scale_factor = max(0.5, 10 / char_count)
            base_size = 60 if self.fonts else 60
            adjusted_size = base_size * scale_factor
            if self.fonts:
                font_main = FontProperties(fname=self.fonts['bold'], size=adjusted_size)
            else:
                font_main = FontProperties(family='monospace', weight='bold', size=adjusted_size)

        # Adjusted Y positions to match Frontend Preview (percentages)
        # Frontend:
        # City Bottom: 14% -> Baseline approx 15-16%?
        # Country Bottom: 10%
        # Coords Bottom: 7%

        ax.text(0.5, 0.15, spaced_city, transform=ax.transAxes,
                color=theme['text'], ha='center', va='baseline', fontproperties=font_main, zorder=11)
        
        ax.plot([0.4, 0.135], [0.6, 0.135], transform=ax.transAxes, 
                 color=accent_color, linewidth=1.5, zorder=11, alpha=0) 
                 # Invisible guide? No, just drawing the separator.
        
        # Separator Line: Frontend says bottom 12.5%.
        ax.plot([0.4, 0.6], [0.125, 0.125], transform=ax.transAxes, 
                color=accent_color, linewidth=1.5, zorder=11)

        # Country: Frontend bottom 10%.
        ax.text(0.5, 0.10, country.upper(), transform=ax.transAxes,
                color=theme['text'], ha='center', va='baseline', fontproperties=font_sub, zorder=11)
        
        # Coords: Frontend bottom 7%.
        lat, lon = point
        coords = f"{lat:.4f}° N / {lon:.4f}° E" if lat >= 0 else f"{abs(lat):.4f}° S / {lon:.4f}° E"
        if lon < 0:
            coords = coords.replace("E", "W")
            
        ax.text(0.5, 0.07, coords, transform=ax.transAxes,
                color=accent_color, alpha=0.7, ha='center', va='baseline', fontproperties=font_coords, zorder=11)

        ax.text(0.98, 0.02, "© OpenStreetMap contributors", transform=ax.transAxes,
                color=theme['text'], alpha=0.5, ha='right', va='bottom', 
                fontproperties=font_attr, zorder=11)
    
    def cleanup(self, wait=True, timeout=30):
        """Cleanup resources, ensuring pending cloud uploads complete.
        
        Args:
            wait: If True, wait for pending uploads to complete
            timeout: Maximum seconds to wait for uploads (default 30)
        """
        if hasattr(self, '_upload_executor'):
            self._upload_executor.shutdown(wait=wait, cancel_futures=not wait)
            print(f"Cloud upload executor shutdown {'with' if wait else 'without'} waiting for pending uploads")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate beautiful map posters")
    parser.add_argument('--city', '-c', required=True, help='City name')
    parser.add_argument('--country', '-C', required=True, help='Country name')
    parser.add_argument('--theme', '-t', default='feature_based', help='Theme name')
    parser.add_argument('--distance', '-d', type=int, default=29000, help='Map radius')
    parser.add_argument('--format', '-f', default='poster_vertical', help='Output format')
    
    args = parser.parse_args()
    
    generator = MapPosterGenerator()
    try:
        path = generator.generate_poster(args.city, args.country, args.theme, args.distance, format_name=args.format)
        print(f"Poster generated: {path}")
    except Exception as e:
        print(f"Error: {e}")
