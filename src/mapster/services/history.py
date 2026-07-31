"""Poster/preview history persisted in Postgres (Neon), replacing local-file scanning.

Local files under posters/ remain the source of the actual image bytes;
this module is the durable record of what was generated (used for the
/history listing and to reconstruct a regeneration request after the
local file is gone, e.g. after a redeploy on an ephemeral filesystem).
"""

from typing import Optional

from mapster.db import session_scope
from mapster.models import Poster


def record_poster(metadata: dict) -> None:
    filename = metadata.get("filename")
    if not filename:
        return
    with session_scope() as db:
        if db.query(Poster).filter_by(filename=filename).one_or_none() is not None:
            return
        db.add(Poster(
            city=metadata.get("city", ""),
            country=metadata.get("country", ""),
            theme=metadata.get("theme") or "",
            distance=int(metadata.get("distance") or 0),
            format_name=metadata.get("format") or metadata.get("format_name") or "poster_vertical",
            filename=filename,
            content_type="image/svg+xml" if filename.endswith(".svg") else "image/png",
            layer_visibility=metadata.get("layer_visibility"),
            custom_colors=metadata.get("custom_colors"),
        ))
        db.commit()


def list_posters(limit: int = 200) -> list[dict]:
    with session_scope() as db:
        rows = db.query(Poster).order_by(Poster.created_at.desc()).limit(limit).all()
        return [row.to_dict() for row in rows]


def get_poster(filename: str) -> Optional[dict]:
    with session_scope() as db:
        row = db.query(Poster).filter_by(filename=filename).one_or_none()
        return row.to_dict() if row else None


def delete_poster(filename: str) -> bool:
    with session_scope() as db:
        row = db.query(Poster).filter_by(filename=filename).one_or_none()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
