"""Pydantic request/response schemas."""

from typing import Optional

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    city: str
    country: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    theme: str = "feature_based"
    distance: int = 29000
    custom_colors: Optional[dict] = None
    layer_visibility: Optional[dict] = None
    format: str = "poster_vertical"
    use_cache: bool = True


class PreviewRequest(BaseModel):
    city: str
    country: str
    distance: int = 12000
    theme: str = "feature_based"
    custom_colors: Optional[dict] = None
    layer_visibility: Optional[dict] = None
    format: str = "poster_vertical"
    use_cache: bool = True


class RestoreRequest(BaseModel):
    filename: str


class AutoDistanceRequest(BaseModel):
    city: str
    country: str
