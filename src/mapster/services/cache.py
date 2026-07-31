"""Postgres (Neon)-backed L2 cache for rendered preview JSON.

Implements the duck-typed remote_cache interface expected by
create_map_poster.MapPosterGenerator: .get(key) / .set(key, data).
Only JSON-serializable payloads are stored — the engine's raw OSM fetch
tier (GeoDataFrames/graphs) is not JSON-safe and is silently skipped,
leaving that tier on local disk only.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from mapster.db import session_scope
from mapster.models import MapCache


def _key_str(cache_key: tuple) -> str:
    return hashlib.sha256(str(cache_key).encode()).hexdigest()


def _extract_city_country(cache_key: tuple) -> tuple[str, str]:
    try:
        city, country = cache_key[0], cache_key[1]
        if isinstance(city, str) and isinstance(country, str):
            return city, country
    except (IndexError, TypeError):
        pass
    return "", ""


class NeonPreviewCache:
    def get(self, cache_key: tuple) -> Optional[Any]:
        key = _key_str(cache_key)
        with session_scope() as db:
            row = db.query(MapCache).filter_by(cache_key=key).one_or_none()
            if row is None:
                return None
            row.access_count += 1
            row.last_accessed_at = datetime.now(timezone.utc)
            db.commit()
            return json.loads(row.data)

    def set(self, cache_key: tuple, data: Any) -> None:
        try:
            payload = json.dumps(data)
        except (TypeError, ValueError):
            return  # not JSON-serializable — skip (e.g. raw fetch tier)

        key = _key_str(cache_key)
        city, country = _extract_city_country(cache_key)
        with session_scope() as db:
            row = db.query(MapCache).filter_by(cache_key=key).one_or_none()
            if row is None:
                db.add(MapCache(cache_key=key, data=payload, city=city, country=country, theme=""))
            else:
                row.data = payload
                row.last_accessed_at = datetime.now(timezone.utc)
            db.commit()


def clear_all() -> int:
    with session_scope() as db:
        count = db.query(MapCache).delete()
        db.commit()
        return count
