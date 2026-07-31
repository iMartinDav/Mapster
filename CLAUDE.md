# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Mapster: a full-stack app that turns a city name into a print-ready map poster. Python/FastAPI backend fetches OpenStreetMap data (via OSMnx/Overpass) and renders SVG previews + high-res PNG posters; React/Vite frontend provides the UI.

## Commands

Tooling: `mise` manages Python 3.11 / Node 22 versions and dev tasks; `uv` manages Python deps (see `pyproject.toml` / `uv.lock`).

    mise install                    # install pinned Python + Node
    mise run install                # uv sync + frontend npm install
    mise run dev                    # run backend + frontend together
    uv run uvicorn mapster.app:app --reload --port 8000   # backend only
    cd frontend && npm run dev      # frontend only (port 5173)
    cd frontend && npm run build
    cd frontend && npm run lint

No test runner is currently installed/configured — see "Test suite" below before assuming `pytest`/`npm test` work.

## Architecture

### Two backend entry points (migration in progress)

- `src/mapster/` is the **current, canonical** backend package — an app-factory FastAPI service (`app.py: create_app()`), used by `Dockerfile`, `railway.json`, and `mise.toml`. Build new backend work here.
  - `app.py` — factory: CORS, mounts routers, mounts `/posters` and `/fonts` static dirs, calls `init_db()` (creates tables on Neon if they don't exist) and starts the job-cleanup background thread.
  - `config.py` — `pydantic-settings` `Settings` (env-driven: `FRONTEND_URL`, `DATABASE_URL`, `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN`, `ADMIN_KEY`, `MAX_CONCURRENT_GENERATIONS`, `JOB_TTL_SECONDS`, ...), cached via `get_settings()`.
  - `routers/` — thin FastAPI routers: `themes`, `jobs` (`/start-preview`, `/start-generate`, `/start-restore`, `/job-status/{id}` — async, thread-per-job, backed by `services/jobs.py`), `history` (`/history`, `/history/{filename}`, `/history/restore`; also legacy synchronous `/preview-data`, `/generate`, `/auto-distance`), `admin` (`/purge-cache`), `thumbnails`.
  - `services/poster.py` — thin wrapper around `create_map_poster.MapPosterGenerator` (root-level file, shared with legacy `api.py`). Constructs the generator with a Neon-backed `remote_cache` (`services/cache.py`) and a `history_hook` (`services/history.py`) — see below.
  - `services/jobs.py` — job status store backed by **Upstash Redis** (TTL-based, auto-expiring, cluster-safe concurrency counter) when `UPSTASH_REDIS_REST_URL`/`TOKEN` are set; otherwise falls back to the original in-memory dict + `threading.Semaphore` (fine for a single local instance, not for multiple server instances). `acquire_slot()`/`release_slot()` gate `MAX_CONCURRENT_GENERATIONS`.
  - `services/cache.py` — `NeonPreviewCache`: Postgres-backed L2 cache for rendered preview JSON (the `MapCache` table), implementing the duck-typed `remote_cache` interface (`get`/`set`) that `MapPosterGenerator` calls into. Only JSON-serializable payloads are stored, so the engine's raw-fetch tier (GeoDataFrames) stays local-disk-only — that's intentional, not a gap.
  - `services/history.py` — durable poster/preview history in the `Poster` table (Neon). `record_poster()` is invoked via the generator's `history_hook` after every successful preview/poster save. `routers/history.py` reads/deletes/restores through this, not by scanning `posters/*.json`.
  - `db.py` — Neon Postgres engine/session. `get_session()` is the FastAPI dependency form; `session_scope()` is a plain context manager for use in services. `init_db()` runs `Base.metadata.create_all()` — there's no Alembic migration in use (see below).
  - `models.py` — SQLAlchemy models: `Poster` (history), `MapCache` (L2 preview cache), `GenerationJob` (defined but unused — job state lives in Redis/memory instead, see `services/jobs.py`).
  - `alembic/` is wired up as empty directories only (no `env.py`/`alembic.ini`/migration scripts) — schema changes currently go through `init_db()`'s `create_all()`, not a migration.

- `api.py` (repo root) is the **legacy** monolithic FastAPI app (imports `MapPosterGenerator` directly, no routers/services split, no Neon/Upstash integration). Still present and functional (falls back to disabled cloud storage/local-only) but superseded by `src/mapster/`; don't add new features here.

### Shared engine (used by both)

- `create_map_poster.py` — `MapPosterGenerator`: the actual map pipeline, and intentionally **storage-agnostic**. Formats are defined in `MAP_FORMATS` (`poster_vertical`, `poster_horizontal`, `desktop`, `phone`). Pipeline: geocode (Nominatim) → fetch roads/water/parks/ocean in parallel (OSMnx/Overpass) → polygonize ocean coastline, subtract ocean from parks → vectorize geometries to SVG paths (NumPy) → return JSON preview (frontend renders SVG) or render a 300 DPI PNG via Matplotlib on demand. Takes two optional constructor hooks so callers can plug in durable storage without coupling the engine to a specific backend:
  - `remote_cache` — duck-typed `.get(key)`/`.set(key, data)`, used as an L2 tier behind the local disk cache (`src/mapster/services/cache.py` supplies the Neon-backed implementation).
  - `history_hook` — callable invoked with a metadata dict after each preview/poster save (`src/mapster/services/history.py` supplies the Neon-backed implementation).

  `api.py` (legacy) constructs the generator with no hooks, so it gets local-disk-only caching and no durable history — that's expected, not a bug.
- `themes/*.json` — 18 theme definitions (colors/styling), loaded by `MapPosterGenerator.load_theme()`.

### Frontend (`frontend/`)

Vite + React 19. `src/App.jsx` is the main desktop UI; `src/components/MobileLayout.jsx` is a parallel mobile UI (shares `ThemeCard`, `useHistoryRestore`, `useIsMobile`). `src/config.js` holds the API base URL (`VITE_API_URL` at build time). Talks to the backend's job-based endpoints (`/start-preview` → poll `/job-status/{id}`, etc.).

### Test suite — currently non-functional scaffolding

`tests/unit`, `tests/integration`, `tests/e2e` exist but:
- `pytest` (and `pytest-asyncio`, `httpx`, `playwright`) are not in `pyproject.toml`'s dependencies — `uv run pytest` fails outright.
- Several tests import modules that don't exist anywhere in the codebase, e.g. `mapster.cache.DatabaseCache` and `mapster.gdal_processor.GDALGeospatialProcessor` — note the real cache module lives at `mapster.services.cache.NeonPreviewCache`, a different shape than what the test expects. Others hit endpoints the app doesn't define (`/health`, `/api/posters`).
- There's no `conftest.py` providing the fixtures the tests expect (`client`, `db_session`, `async_db`, `sample_poster_data`).

Don't assume this suite passes or reflects real behavior — verify against the actual routers/models above before trusting a test file's imports. If asked to fix or extend tests, this gap will need addressing first (add test deps, write fixtures, or prune tests referencing nonexistent modules).

## Cloud infrastructure

- **Neon Postgres** — durable store for poster/preview history (`Poster` table) and the L2 preview-JSON cache (`MapCache` table). Required; `DATABASE_URL` (sync, psycopg2) is what `db.py` actually uses — `DATABASE_URL_ASYNC` is defined in `Settings` but nothing currently uses an async engine.
- **Upstash Redis** — job status + cluster-wide concurrency limiting for `/start-preview`/`/start-generate`/`/start-restore`. Optional: unset `UPSTASH_REDIS_REST_URL`/`TOKEN` and the app transparently falls back to in-memory (single-instance only).
- No blob storage service is used for the actual PNG/SVG files — they live only in the local `posters/`/`cache/` directories, which are ephemeral on redeploy for hosts like Railway. This is a deliberate tradeoff (durability lives in Neon's *metadata*, not the *pixels*); restoring an item whose local file is gone re-renders it from Overpass via the Postgres-stored metadata rather than serving a cached image instantly.
- Supabase (previously used for both a cloud cache mirror and poster file backup) has been fully removed — `supabase_storage.py` and `services/storage.py` no longer exist.

## Deployment

- `Dockerfile`: `uv`-based build targeting `src/mapster` + the shared root files it needs (`create_map_poster.py`, `generate_previews.py`, `themes/`, `fonts/`, `data/`). `PYTHONPATH=/app/src`, entrypoint `uv run python -m mapster.main`. Needs `DATABASE_URL` (and optionally `UPSTASH_REDIS_REST_URL`/`TOKEN`) set in the deployment environment.
- `railway.json`: uses the Dockerfile; healthcheck path is `/themes` (there is no `/health` endpoint despite what the tests assume).
- Frontend deploys separately (e.g. Vercel) with `VITE_API_URL` pointed at the backend.
