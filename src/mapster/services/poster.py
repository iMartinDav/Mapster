"""Poster generation service — wraps create_map_poster.MapPosterGenerator."""

import gc
import os
from typing import Any, Callable, Optional

from create_map_poster import MapPosterGenerator

from mapster.services import cache, geodata, history

_generator: Optional[MapPosterGenerator] = None


def get_generator() -> MapPosterGenerator:
    global _generator
    if _generator is None:
        _generator = MapPosterGenerator(
            remote_cache=cache.NeonPreviewCache(),
            history_hook=history.record_poster,
            geo_store=geodata.PostgisGeoStore(),
        )
    return _generator


def trim_cache(max_entries: int = 2):
    get_generator().trim_memory_cache(max_entries=max_entries)
    gc.collect()


def get_available_themes() -> list[str]:
    return get_generator().get_available_themes()


def load_theme(theme_name: str) -> dict:
    return get_generator().load_theme(theme_name)


def compute_auto_distance(city: str, country: str):
    return get_generator().compute_auto_distance(city, country)


def get_preview_data(
    city: str,
    country: str,
    distance: int,
    layer_visibility: Any,
    fmt: str,
    *,
    use_cache: bool = True,
    theme_name: Optional[str] = None,
    custom_colors: Optional[dict] = None,
    callback: Optional[Callable] = None,
) -> dict:
    return get_generator().get_preview_data(
        city,
        country,
        distance,
        layer_visibility,
        fmt,
        callback=callback,
        use_cache=use_cache,
        theme_name=theme_name,
        custom_colors=custom_colors,
    )


def generate_poster(
    city: str,
    country: str,
    theme: str,
    distance: int,
    custom_colors: Optional[dict],
    layer_visibility: Optional[dict],
    format_name: str,
    *,
    use_cache: bool = True,
    callback: Optional[Callable] = None,
) -> str:
    return get_generator().generate_poster(
        city,
        country,
        theme,
        distance,
        custom_colors,
        layer_visibility,
        format_name,
        callback=callback,
        use_cache=use_cache,
    )


def purge_all_cache() -> dict:
    gen = get_generator()
    results = {}

    gen.data_cache.clear()
    results["memory_cache"] = "cleared"

    try:
        results["neon_cache_rows_deleted"] = cache.clear_all()
    except Exception as e:
        results["neon_cache_error"] = str(e)

    cache_dir = gen.cache_dir
    deleted_cache = 0
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            try:
                os.remove(os.path.join(cache_dir, f))
                deleted_cache += 1
            except Exception:
                pass
    results["local_cache_files_deleted"] = deleted_cache

    posters_dir = gen.posters_dir
    deleted_posters = 0
    if os.path.exists(posters_dir):
        for f in os.listdir(posters_dir):
            try:
                os.remove(os.path.join(posters_dir, f))
                deleted_posters += 1
            except Exception:
                pass
    results["local_poster_files_deleted"] = deleted_posters

    return results
