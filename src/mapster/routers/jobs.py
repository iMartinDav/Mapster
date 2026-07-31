"""Async job routes (start-preview, start-generate, start-restore, job-status)."""

import json
import os
import threading

from fastapi import APIRouter

from mapster.schemas import GenerateRequest, PreviewRequest, RestoreRequest
from mapster.services import history, jobs, poster
from mapster.services.jobs import acquire_slot, release_slot, get_job, update_job, complete_job, fail_job

router = APIRouter(tags=["jobs"])


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

def _background_preview_task(job_id, city, country, distance, visibility, fmt, use_cache, theme, custom_colors):
    if not acquire_slot():
        fail_job(job_id, "Server is busy generating other maps. Please try again in a moment.")
        return
    try:
        poster.trim_cache()

        def cb(msg, pct, partial=None):
            update_job(job_id, msg, pct, partial)

        data = poster.get_preview_data(
            city, country, distance, visibility, fmt,
            callback=cb, use_cache=use_cache,
            theme_name=theme, custom_colors=custom_colors,
        )
        complete_job(job_id, data)
    except Exception as e:
        fail_job(job_id, str(e))
        print(f"Job {job_id} failed: {e}")
    finally:
        poster.trim_cache()
        release_slot()


def _background_generate_task(job_id, req: GenerateRequest):
    if not acquire_slot():
        fail_job(job_id, "Server is busy generating other maps. Please try again in a moment.")
        return
    try:
        poster.trim_cache()

        path = poster.generate_poster(
            req.city, req.country, req.theme, req.distance,
            req.custom_colors, req.layer_visibility, req.format,
            callback=lambda msg, pct: update_job(job_id, msg, pct),
            use_cache=req.use_cache,
            lat=req.lat,
            lon=req.lon,
        )

        filename = os.path.basename(path)
        result = {"status": "success", "image_url": f"/posters/{filename}", "filename": filename}
        complete_job(job_id, result)
    except Exception as e:
        fail_job(job_id, str(e))
    finally:
        poster.trim_cache()
        release_slot()


def _background_restore_task(job_id, filename):
    if not acquire_slot():
        fail_job(job_id, "Server is busy generating other maps. Please try again in a moment.")
        return
    try:
        poster.trim_cache()

        posters_dir = "posters"
        base_name = os.path.splitext(filename)[0]
        json_path = os.path.join(posters_dir, f"{base_name}.json")

        update_job(job_id, "Loading metadata...", 10)

        if not os.path.exists(json_path):
            preview_path = os.path.join(posters_dir, f"{base_name}.preview.json")
            if os.path.exists(preview_path):
                update_job(job_id, "Found legacy preview data...", 30)
                with open(preview_path) as f:
                    data = json.load(f)
                complete_job(job_id, data)
                return

            db_meta = history.get_poster(filename)
            if db_meta:
                update_job(job_id, "Found metadata in database, saving locally...", 30)
                with open(json_path, "w") as f:
                    json.dump(db_meta, f)
            else:
                fail_job(job_id, "Map metadata not found locally or in the database")
                return

        update_job(job_id, "Reading metadata...", 40)
        with open(json_path) as f:
            meta = json.load(f)

        update_job(job_id, "Loading map cache...", 50)

        def cb(msg, pct, partial=None):
            scaled = 50 + int(pct * 0.45)
            update_job(job_id, msg, scaled, partial)

        data = poster.get_preview_data(
            meta["city"], meta["country"],
            meta.get("distance", 12000),
            meta.get("layer_visibility"),
            meta.get("format") or meta.get("format_name", "poster_vertical"),
            use_cache=False,
            theme_name=meta.get("theme"),
            custom_colors=meta.get("custom_colors"),
            callback=cb,
        )

        complete_job(job_id, data)

    except Exception as e:
        fail_job(job_id, str(e))
        print(f"Restore job {job_id} failed: {e}")
    finally:
        poster.trim_cache()
        release_slot()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start-preview")
def start_preview(request: PreviewRequest):
    job_id = jobs.create_job("preview")
    thread = threading.Thread(
        target=_background_preview_task,
        args=(job_id, request.city, request.country, request.distance,
              request.layer_visibility, request.format, request.use_cache,
              request.theme, request.custom_colors),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@router.post("/start-generate")
def start_generate(request: GenerateRequest):
    job_id = jobs.create_job("generate")
    thread = threading.Thread(
        target=_background_generate_task,
        args=(job_id, request),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@router.post("/start-restore")
def start_restore(request: RestoreRequest):
    job_id = jobs.create_job("restore", "Initializing restore...")
    thread = threading.Thread(
        target=_background_restore_task,
        args=(job_id, request.filename),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@router.get("/job-status/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        return {
            "status": "failed",
            "error": "Job not found \u2014 the server may have restarted. Please try again.",
            "progress": 0,
            "message": "Job expired",
        }
    return job
