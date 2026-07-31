"""Thumbnail routes."""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image

router = APIRouter(tags=["thumbnails"])


@router.get("/thumbnails/{filename}")
def get_thumbnail(filename: str):
    posters_dir = "posters"
    thumbs_dir = os.path.join(posters_dir, "thumbnails")
    os.makedirs(thumbs_dir, exist_ok=True)

    thumb_path = os.path.join(thumbs_dir, filename)

    if filename.endswith(".svg"):
        original_path = os.path.join(posters_dir, filename)
        return FileResponse(original_path)

    if not os.path.exists(thumb_path):
        original_path = os.path.join(posters_dir, filename)
        if not os.path.exists(original_path):
            raise HTTPException(status_code=404, detail="Original file not found")
        try:
            with Image.open(original_path) as img:
                img.thumbnail((500, 300))
                img.save(thumb_path)
        except Exception:
            return FileResponse(original_path)

    return FileResponse(thumb_path)
