"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mapster.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Poster(Base):
    __tablename__ = "posters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    city: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(255))
    theme: Mapped[str] = mapped_column(String(100))
    distance: Mapped[int] = mapped_column(Integer)
    format_name: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(50))
    layer_visibility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    custom_colors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "city": self.city,
            "country": self.country,
            "theme": self.theme,
            "distance": self.distance,
            "format_name": self.format_name,
            "filename": self.filename,
            "image_url": f"/posters/{self.filename}",
            "thumbnail_url": f"/thumbnails/{self.filename}",
            "custom_colors": self.custom_colors,
            "layer_visibility": self.layer_visibility,
            "created_at": self.created_at.isoformat(),
            "timestamp": self.created_at.timestamp(),
        }

    def __repr__(self):
        return f"<Poster {self.city}, {self.country} ({self.theme})>"


class MapCache(Base):
    __tablename__ = "map_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    data: Mapped[str] = mapped_column(String)  # JSON string
    city: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(255))
    theme: Mapped[str] = mapped_column(String(100))
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self):
        return f"<MapCache {self.cache_key} ({self.city}, {self.country})>"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(500), default="")
    request_type: Mapped[str] = mapped_column(String(50))
    request_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "request_type": self.request_type,
            "created_at": self.created_at.isoformat(),
        }
        if self.result:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error
        return d

    def __repr__(self):
        return f"<GenerationJob {self.id} ({self.status})>"
