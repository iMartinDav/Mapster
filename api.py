from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from create_map_poster import MapPosterGenerator
import gc
import os
import uvicorn
import json
from typing import Optional
import uuid
import threading
import time
from PIL import Image

# Cloud storage support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase_storage import SupabaseStorage
    cloud_storage = SupabaseStorage()
    USE_CLOUD_STORAGE = True
    print("☁️ API: Cloud storage enabled")
except Exception as e:
    cloud_storage = None
    USE_CLOUD_STORAGE = False
    print(f"⚠️ API: Cloud storage unavailable: {e}")

app = FastAPI(title="City Map Poster API")

# CORS: restrict to frontend URL(s) in production, allow all in development
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
custom_domain = os.environ.get("CUSTOM_DOMAIN", "")
allowed_origins = [frontend_url]
if custom_domain:
    allowed_origins.append(custom_domain)
if "localhost" in frontend_url:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize generator
generator = MapPosterGenerator()

# Mount static files for posters
os.makedirs("posters", exist_ok=True)
app.mount("/posters", StaticFiles(directory="posters"), name="posters")

# --- Job Management ---
jobs = {}

# Concurrency limiter: prevent OOM from too many simultaneous generations
# Set to 1 to halve peak memory usage (large cities can use 150-200MB each)
MAX_CONCURRENT_GENERATIONS = 1
_generation_semaphore = threading.Semaphore(MAX_CONCURRENT_GENERATIONS)

# Job cleanup: remove completed/failed jobs after 30 minutes
JOB_TTL_SECONDS = 30 * 60

def _periodic_cleanup():
    """Background thread to periodically clean up old jobs."""
    while True:
        time.sleep(5 * 60)  # Run every 5 minutes
        try:
            _cleanup_old_jobs()
        except Exception as e:
            print(f"Periodic cleanup failed: {e}")

# Start background cleanup thread
cleanup_thread = threading.Thread(target=_periodic_cleanup, daemon=True)
cleanup_thread.start()

def _cleanup_old_jobs():
    """Remove completed/failed jobs older than JOB_TTL_SECONDS."""
    now = time.time()
    to_delete = [
        jid for jid, job in jobs.items()
        if job['status'] in ('completed', 'failed')
        and now - job.get('created_at', 0) > JOB_TTL_SECONDS
    ]
    for jid in to_delete:
        del jobs[jid]

def update_job_progress(job_id, message, percent, partial_data=None):
    if job_id in jobs:
        jobs[job_id]['progress'] = percent
        jobs[job_id]['message'] = message
        if partial_data is not None:
            jobs[job_id]['partial_data'] = partial_data

def background_preview_task(job_id, city, country, distance, visibility, fmt, use_cache, theme, custom_colors):
    if not _generation_semaphore.acquire(timeout=0):
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = 'Server is busy generating other maps. Please try again in a moment.'
        return
    try:
        # Trim cache BEFORE processing to free memory for large cities
        generator.trim_memory_cache(max_entries=2)
        gc.collect()

        def progress_callback(msg, pct, partial=None):
            update_job_progress(job_id, msg, pct, partial)

        data = generator.get_preview_data(
            city, country, distance, visibility, fmt,
            callback=progress_callback,
            use_cache=use_cache,
            theme_name=theme,
            custom_colors=custom_colors
        )
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['result'] = data
        jobs[job_id]['progress'] = 100
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
        print(f"Job {job_id} failed: {e}")
    finally:
        generator.trim_memory_cache(max_entries=2)
        gc.collect()
        _generation_semaphore.release()

def background_generate_task(job_id, request_data):
    if not _generation_semaphore.acquire(timeout=0):
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = 'Server is busy generating other maps. Please try again in a moment.'
        return
    try:
        # Trim cache BEFORE processing to free memory for large cities
        generator.trim_memory_cache(max_entries=2)
        gc.collect()

        # Validate theme
        if request_data.theme not in generator.get_available_themes():
            pass # fallback handled in generator

        path = generator.generate_poster(
            request_data.city,
            request_data.country,
            request_data.theme,
            request_data.distance,
            request_data.custom_colors,
            request_data.layer_visibility,
            request_data.format,
            callback=lambda msg, pct: update_job_progress(job_id, msg, pct),
            use_cache=request_data.use_cache
        )

        filename = os.path.basename(path)
        result = {
            "status": "success",
            "image_url": f"/posters/{filename}",
            "filename": filename
        }

        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['result'] = result
        jobs[job_id]['progress'] = 100
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
    finally:
        generator.trim_memory_cache(max_entries=2)
        gc.collect()
        _generation_semaphore.release()

def background_restore_task(job_id, filename):
    """Background task for restoring a history item with progress updates."""
    if not _generation_semaphore.acquire(timeout=0):
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = 'Server is busy generating other maps. Please try again in a moment.'
        return
    try:
        # Trim cache BEFORE processing to free memory for large cities
        generator.trim_memory_cache(max_entries=2)
        gc.collect()

        posters_dir = "posters"
        base_name = os.path.splitext(filename)[0]

        update_job_progress(job_id, 'Loading metadata...', 10)

        # Try to find local JSON metadata first
        json_path = os.path.join(posters_dir, f"{base_name}.json")

        if not os.path.exists(json_path):
            # Fallback for old PNGs
            preview_path = os.path.join(posters_dir, f"{base_name}.preview.json")
            if os.path.exists(preview_path):
                update_job_progress(job_id, 'Found legacy preview data...', 30)
                with open(preview_path, 'r') as f:
                    data = json.load(f)
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['result'] = data
                jobs[job_id]['progress'] = 100
                return

            # Try to fetch from Supabase if not found locally
            if USE_CLOUD_STORAGE and cloud_storage:
                update_job_progress(job_id, 'Checking cloud storage...', 20)
                cloud_meta = cloud_storage.load_json(f"{base_name}.json")
                if cloud_meta:
                    update_job_progress(job_id, 'Found cloud metadata, saving locally...', 30)
                    # Save to local for future fast access
                    with open(json_path, 'w') as f:
                        json.dump(cloud_meta, f)
                else:
                    jobs[job_id]['status'] = 'failed'
                    jobs[job_id]['error'] = 'Map metadata not found locally or in cloud'
                    return
            else:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['error'] = 'Map metadata not found'
                return

        update_job_progress(job_id, 'Reading metadata...', 40)
        with open(json_path, 'r') as f:
            meta = json.load(f)

        update_job_progress(job_id, 'Loading map cache...', 50)

        # Generate preview data with progress callback
        def restore_callback(msg, pct, partial=None):
            # Scale progress: 50-95% for the actual generation
            scaled_pct = 50 + int(pct * 0.45)
            update_job_progress(job_id, msg, scaled_pct, partial)

        data = generator.get_preview_data(
            meta['city'], meta['country'],
            meta.get('distance', 12000),
            meta.get('layer_visibility'),
            meta.get('format', 'poster_vertical'),
            use_cache=False,  # Always generate fresh for restore (ignore stale cache)
            theme_name=meta.get('theme'),
            custom_colors=meta.get('custom_colors'),
            callback=restore_callback
        )

        update_job_progress(job_id, 'Complete!', 100)
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['result'] = data
        jobs[job_id]['progress'] = 100

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)
        print(f"Restore job {job_id} failed: {e}")
    finally:
        generator.trim_memory_cache(max_entries=2)
        gc.collect()
        _generation_semaphore.release()

# --- Models ---

class GenerateRequest(BaseModel):
    city: str
    country: str
    theme: str = "feature_based"
    distance: int = 29000
    custom_colors: Optional[dict] = None
    layer_visibility: Optional[dict] = None
    format: str = "poster_vertical"
    use_cache: bool = True  # New field for cache control

class PreviewRequest(BaseModel):
    city: str
    country: str
    distance: int = 12000
    theme: str = "feature_based"
    custom_colors: Optional[dict] = None
    layer_visibility: Optional[dict] = None
    format: str = "poster_vertical"
    use_cache: bool = True  # New field for cache control

class RestoreRequest(BaseModel):
    filename: str

class AutoDistanceRequest(BaseModel):
    city: str
    country: str

# --- Endpoints ---

@app.get("/themes")
def get_themes():
    themes = []
    for theme_name in generator.get_available_themes():
        theme_data = generator.load_theme(theme_name)
        display_name = theme_data.get('name', theme_name.replace('_', ' ').title())
        
        themes.append({
            "id": theme_name,
            "name": display_name,
            "preview_url": f"/themes/{theme_name}.png",
            **theme_data
        })
    return {"themes": themes}

@app.post("/auto-distance")
def get_auto_distance(request: AutoDistanceRequest):
    """Compute an appropriate zoom distance based on the city's geographic extent."""
    try:
        distance, lat, lon = generator.compute_auto_distance(request.city, request.country)
        return {"distance": distance, "lat": lat, "lon": lon}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-distance failed: {str(e)}")

@app.get("/thumbnails/{filename}")
def get_thumbnail(filename: str):
    posters_dir = "posters"
    thumbs_dir = os.path.join(posters_dir, "thumbnails")
    os.makedirs(thumbs_dir, exist_ok=True)
    
    thumb_path = os.path.join(thumbs_dir, filename)
    
    # If SVG, return original directly (no resizing needed)
    if filename.endswith('.svg'):
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
        except Exception as e:
             return FileResponse(original_path)

    return FileResponse(thumb_path)

@app.get("/history")
def get_history():
    """Return history from LOCAL storage only for fast user experience."""
    files = []
    posters_dir = "posters"

    if os.path.exists(posters_dir):
        for f in os.listdir(posters_dir):
            if f.endswith('.svg'):
                path = os.path.join(posters_dir, f)
                metadata = {}
                base_name = os.path.splitext(f)[0]
                json_path = os.path.join(posters_dir, f"{base_name}.json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as jf:
                            metadata = json.load(jf)
                    except:
                        pass

                # Fallback: parse city from filename if no metadata
                # e.g., "preview_Winnipeg.svg" -> "Winnipeg"
                if 'city' not in metadata:
                    city_from_filename = base_name.replace('preview_', '').replace('_', ' ')
                    metadata['city'] = city_from_filename

                item = {
                    "filename": f,
                    "image_url": f"/posters/{f}",
                    "thumbnail_url": f"/thumbnails/{f}",
                    "source": "local",
                    **metadata,
                    "timestamp": metadata.get('timestamp', os.path.getmtime(path))
                }
                files.append(item)

    files.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    return {"history": files}

@app.delete("/history/{filename}")
def delete_history_item(filename: str):
    deleted = False
    base_name = os.path.splitext(filename)[0]
    
    # Try to delete from cloud storage
    if USE_CLOUD_STORAGE and cloud_storage:
        try:
            if cloud_storage.delete_poster(filename):
                deleted = True
            # Also delete associated metadata
            cloud_storage.delete_poster(f"{base_name}.json")
        except Exception as e:
            print(f"Cloud delete failed: {e}")
    
    # Also try local deletion
    posters_dir = "posters"
    thumbs_dir = os.path.join(posters_dir, "thumbnails")
    file_path = os.path.join(posters_dir, filename)
    thumb_path = os.path.join(thumbs_dir, filename)
    json_path = os.path.join(posters_dir, f"{base_name}.json")
    
    if os.path.exists(file_path):
        os.remove(file_path)
        deleted = True
    if os.path.exists(thumb_path):
        try: os.remove(thumb_path)
        except: pass
    if os.path.exists(json_path):
        try: os.remove(json_path)
        except: pass
            
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "success", "message": f"Deleted {filename}"}

@app.post("/history/restore")
def restore_history(request: RestoreRequest):
    posters_dir = "posters"
    
    # Clean cleanup of extension to get base name
    # We might have .png or .svg or even .json passed in
    base_name = os.path.splitext(request.filename)[0]
    
    # 1. Try to find a pre-generated preview JSON (Level 2 cache-ish)
    # The convention for history previews is `preview_{City}.json`
    # The convention for posters is `{City}_...preview.json` sometimes?
    
    # Let's try the direct metadata match first
    json_path = os.path.join(posters_dir, f"{base_name}.json")
    
    # If the file passed was `preview_City.svg`, we are looking for `preview_City.json`
    # That file contains metadata AND if it was a preview, the actual `preview_json` logic isn't saved there?
    # Wait, `get_preview_data` returns the huge JSON. 
    # `_save_preview_history` only saves metadata to `{base}.json`.
    # AND `_generate_preview_json` saves result to Level 2 Cache (disk).
    
    if not os.path.exists(json_path):
        # Fallback for old PNGs: they might have a separate .preview.json
        preview_path = os.path.join(posters_dir, f"{base_name}.preview.json")
        if os.path.exists(preview_path):
             with open(preview_path, 'r') as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="Map metadata not found")
        
    try:
        with open(json_path, 'r') as f:
            meta = json.load(f)
            
        # If this was a "preview" type, we can re-generate it using cache instantly
        # passed theme/colors will be in 'meta'
        return generator.get_preview_data(
            meta['city'], meta['country'],
            meta.get('distance', 12000),
            meta.get('layer_visibility'),
            meta.get('format', 'poster_vertical'),
            use_cache=True, # Critical: use cache to be fast
            theme_name=meta.get('theme'),
            custom_colors=meta.get('custom_colors')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")

# --- New Async Endpoints ---

@app.post("/start-restore")
def start_restore(request: RestoreRequest):
    """Async endpoint for restoring history with progress updates."""
    _cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'running',
        'progress': 0,
        'message': 'Initializing restore...',
        'type': 'restore',
        'created_at': time.time()
    }

    thread = threading.Thread(
        target=background_restore_task,
        args=(job_id, request.filename)
    )
    thread.daemon = True
    thread.start()

    return {"job_id": job_id}

@app.post("/start-preview")
def start_preview(request: PreviewRequest):
    _cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'running',
        'progress': 0,
        'message': 'Initializing...',
        'type': 'preview',
        'created_at': time.time()
    }
    
    thread = threading.Thread(
        target=background_preview_task,
        args=(job_id, request.city, request.country, request.distance, request.layer_visibility, request.format, request.use_cache, request.theme, request.custom_colors)
    )
    thread.daemon = True
    thread.start()
    
    return {"job_id": job_id}

@app.post("/start-generate")
def start_generate(request: GenerateRequest):
    _cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'running',
        'progress': 0,
        'message': 'Initializing...',
        'type': 'generate',
        'created_at': time.time()
    }
    
    thread = threading.Thread(
        target=background_generate_task,
        args=(job_id, request)
    )
    thread.daemon = True
    thread.start()
    
    return {"job_id": job_id}

@app.get("/job-status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in jobs:
        # Return a "failed" status instead of 404 so even old frontend code
        # (without explicit 404 handling) stops polling immediately.
        return {
            "status": "failed",
            "error": "Job not found — the server may have restarted. Please try again.",
            "progress": 0,
            "message": "Job expired"
        }
    return jobs[job_id]

# --- Legacy/Blocking Endpoints (kept for compatibility logic if needed, but updated to use async flow logic internally to not block?) ---
# Actually, we can keep them blocking for now if frontend switches to new ones.
# Or we can make them wrappers.
@app.post("/preview-data")
def get_preview_data_blocking(request: PreviewRequest):
    try:
        data = generator.get_preview_data(
            request.city,
            request.country,
            request.distance,
            request.layer_visibility,
            request.format,
            use_cache=request.use_cache
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate")
def generate_poster_blocking(request: GenerateRequest):
    try:
        # Validate theme
        available_themes = generator.get_available_themes()
        if request.theme not in available_themes:
            # Fallback or error?
            pass 

        output_path = generator.generate_poster(
            request.city, 
            request.country, 
            request.theme, 
            request.distance,
            request.custom_colors,  # Pass custom colors
            request.layer_visibility,
            format_name=request.format,
            use_cache=request.use_cache
        )
        
        filename = os.path.basename(output_path)
        return {
            "status": "success", 
            "image_url": f"/posters/{filename}",
            "filename": filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/purge-cache")
async def purge_cache(admin_key: str = ""):
    """Purge all cached data: local disk cache, memory cache, Supabase cache bucket, and local posters."""
    # Simple admin key check (set ADMIN_KEY env var on server)
    expected_key = os.environ.get("ADMIN_KEY", "")
    if expected_key and admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    results = {}

    # 1. Clear in-memory cache
    generator.data_cache.clear()
    results["memory_cache"] = "cleared"

    # 2. Clear local disk cache (cache/*.pkl)
    cache_dir = generator.cache_dir
    deleted_cache = 0
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            try:
                os.remove(os.path.join(cache_dir, f))
                deleted_cache += 1
            except Exception:
                pass
    results["local_cache_files_deleted"] = deleted_cache

    # 3. Clear local posters (posters/*.png, *.svg, *.json)
    posters_dir = generator.posters_dir
    deleted_posters = 0
    if os.path.exists(posters_dir):
        for f in os.listdir(posters_dir):
            try:
                os.remove(os.path.join(posters_dir, f))
                deleted_posters += 1
            except Exception:
                pass
    results["local_poster_files_deleted"] = deleted_posters

    # 4. Purge Supabase storage buckets
    if USE_CLOUD_STORAGE and cloud_storage:
        for bucket_name in [cloud_storage.cache_bucket, cloud_storage.posters_bucket]:
            try:
                files = cloud_storage.client.storage.from_(bucket_name).list(options={"limit": 1000})
                if files:
                    filenames = [f["name"] for f in files if f.get("name")]
                    if filenames:
                        cloud_storage.client.storage.from_(bucket_name).remove(filenames)
                        results[f"supabase_{bucket_name}_deleted"] = len(filenames)
                    else:
                        results[f"supabase_{bucket_name}_deleted"] = 0
                else:
                    results[f"supabase_{bucket_name}_deleted"] = 0
            except Exception as e:
                results[f"supabase_{bucket_name}_error"] = str(e)
        # Clear Supabase memory cache too
        cloud_storage._memory_cache.clear()
    else:
        results["supabase"] = "not connected"

    return {"status": "purged", "details": results}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
