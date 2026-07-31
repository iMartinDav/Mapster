"""History routes and blocking legacy endpoints."""

import json
import os

from fastapi import APIRouter, HTTPException

from mapster.schemas import GenerateRequest, PreviewRequest, RestoreRequest
from mapster.services import history, poster

router = APIRouter(tags=["history"])


@router.get("/history")
def get_history():
    return {"history": history.list_posters()}


@router.delete("/history/{filename}")
def delete_history_item(filename: str):
    deleted = False
    base_name = os.path.splitext(filename)[0]

    posters_dir = "posters"
    thumbs_dir = os.path.join(posters_dir, "thumbnails")
    file_path = os.path.join(posters_dir, filename)
    thumb_path = os.path.join(thumbs_dir, filename)
    json_path = os.path.join(posters_dir, f"{base_name}.json")
    preview_json_path = os.path.join(posters_dir, f"{base_name}.preview.json")

    if os.path.exists(file_path):
        os.remove(file_path)
        deleted = True
    for path in (thumb_path, json_path, preview_json_path):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    if history.delete_poster(filename):
        deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "success", "message": f"Deleted {filename}"}


@router.post("/history/restore")
def restore_history(request: RestoreRequest):
    posters_dir = "posters"
    base_name = os.path.splitext(request.filename)[0]
    json_path = os.path.join(posters_dir, f"{base_name}.json")

    if os.path.exists(json_path):
        with open(json_path) as f:
            meta = json.load(f)
    else:
        preview_path = os.path.join(posters_dir, f"{base_name}.preview.json")
        if os.path.exists(preview_path):
            with open(preview_path) as f:
                return json.load(f)
        meta = history.get_poster(request.filename)
        if meta is None:
            raise HTTPException(status_code=404, detail="Map metadata not found")

    try:
        return poster.get_preview_data(
            meta["city"], meta["country"],
            meta.get("distance", 12000),
            meta.get("layer_visibility"),
            meta.get("format") or meta.get("format_name", "poster_vertical"),
            use_cache=True,
            theme_name=meta.get("theme"),
            custom_colors=meta.get("custom_colors"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")


@router.post("/preview-data")
def preview_data_blocking(request: PreviewRequest):
    try:
        return poster.get_preview_data(
            request.city, request.country, request.distance,
            request.layer_visibility, request.format,
            use_cache=request.use_cache,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
def generate_poster_blocking(request: GenerateRequest):
    try:
        output_path = poster.generate_poster(
            request.city, request.country, request.theme, request.distance,
            request.custom_colors, request.layer_visibility,
            format_name=request.format, use_cache=request.use_cache,
        )
        filename = os.path.basename(output_path)
        return {"status": "success", "image_url": f"/posters/{filename}", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-distance")
def get_auto_distance(request: PreviewRequest):
    try:
        distance, lat, lon = poster.compute_auto_distance(request.city, request.country)
        return {"distance": distance, "lat": lat, "lon": lon}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-distance failed: {str(e)}")
