# Mapster

**Transform any city into a stunning, print-ready map poster.**

A full-stack web application for creating high-resolution map posters of cities worldwide. Built with React, FastAPI, and powered by OpenStreetMap data.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/P5P51SSYA9)

<p align="center">
  <img src="https://github.com/MartinDAVILA/Map2Poster/releases/download/v1.0.0/Map2Poster.gif" alt="Map2Poster Demo" width="800">
</p>

---

## Screenshots

<p align="center">
  <img src="docs/screenshots/Map2Poster-2.jpg" alt="Toronto — Blueprint theme" width="800">
</p>
<p align="center">
  <img src="docs/screenshots/Map2Poster-3.jpg" alt="Toronto — Midnight Blue theme" width="800">
</p>
<p align="center">
  <img src="docs/screenshots/Map2Poster-4.jpg" alt="Washington — Neon Cyberpunk theme" width="800">
</p>

---

## Features

- **18 Themes** — From minimalist noir to vibrant neon cyberpunk, with full custom color override support
- **Real-Time SVG Preview** — Watch your map render layer-by-layer; switch themes and colors instantly without re-fetching data
- **Global Coverage** — Generate maps for any city in the world using OpenStreetMap data via OSMnx
- **4 Formats** — Vertical Poster (3:4), Horizontal Poster (4:3), Desktop Wallpaper (16:9), Phone Wallpaper (9:16) — all at 300 DPI
- **Layer Controls** — Toggle motorways, primary/secondary/tertiary roads, water, ocean, and parks independently
- **Smart Caching** — Two-level cache (raw OSM data on disk, rendered preview backed by Neon Postgres) so repeat requests skip the Overpass API entirely
- **History** — Automatically saves SVG thumbnails and metadata with one-click restoration

---

## Self-Hosting Guide

Mapster runs as two processes: a **Python backend** (FastAPI) that fetches OSM data and generates maps, and a **React frontend** (Vite) that provides the UI. Both run locally with no external services required.

### Prerequisites

- **[mise](https://mise.jdx.dev/)** (dev tool version manager) — installs Python, Node.js, and runs tasks
- **[uv](https://docs.astral.sh/uv/)** (Python package manager) — fast, reliable dependency management
- **GDAL/GEOS/PROJ** system libraries (required by GeoPandas/Shapely)

#### Installing System Dependencies

**macOS** (via Homebrew):
```bash
brew install gdal geos proj
```

**Ubuntu/Debian**:
```bash
sudo apt-get install -y libgdal-dev libgeos-dev libproj-dev gcc g++
```

**Windows**: Install via [OSGeo4W](https://trac.osgeo.org/osgeo4w/) or use WSL with the Ubuntu instructions above.

#### Installing mise and uv

```bash
# macOS / Linux
curl https://mise.run | sh

# uv (via mise or standalone)
mise use -g uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/MartinDAVILA/Map2Poster.git
   cd Map2Poster
   ```

2. **Install tools and dependencies**
   ```bash
   mise install          # installs pinned Python + Node.js versions
   uv sync               # installs Python dependencies into .venv
   cd frontend && npm install && cd ..   # installs frontend dependencies
   ```

   Or use the mise task:
   ```bash
   mise run install      # runs uv sync + frontend npm install
   ```

### Running Locally

The easiest way is the mise task that starts both backend and frontend:

```bash
mise run dev
```

Or run them separately:

**Terminal 1 — Backend:**
```bash
uv run uvicorn mapster.app:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend && npm run dev
```

The API server starts at `http://localhost:8000` and the frontend at `http://localhost:5173`. The frontend automatically connects to the backend (configured in `frontend/src/config.js`).

### That's It

Enter a city and country, click **Create Preview**, and your map will generate. No API keys, no accounts, no external services needed. All data comes from the free OpenStreetMap Overpass API.

> **A note on generation speed:** Map generation speed is largely dependent on the [Overpass API](https://overpass-api.de/) (OpenStreetMap's public data server), which processes and returns road, water, park, and coastline data. The application itself is optimized — data is fetched in parallel, geometry processing is batched and vectorized, and a two-level cache ensures repeat requests are near-instant — but the Overpass API response time is the primary bottleneck and is outside the application's control.

---

## Cloud Storage & Job Queue (Neon + Upstash)

Generated poster/preview **image files** always live locally in `posters/` and `cache/` (lost on redeploy for ephemeral hosts — that's expected). Durable state lives in two managed services:

- **[Neon](https://neon.tech)** (serverless Postgres) — history metadata (what you generated, when) and a second-tier cache of rendered preview JSON, so repeat requests skip the Overpass API even after a redeploy.
- **[Upstash](https://upstash.com)** (serverless Redis) — job status for async preview/generate/restore requests, and the concurrency limiter. Optional: without it the app falls back to an in-memory job store (fine for a single local instance, not for multiple server instances).

Setup:

1. Create a Neon project (console, or the Neon MCP/CLI) and copy its pooled connection string.
2. Create an Upstash Redis database (`upstash login`, then `upstash redis create --name mapster --region <region>`) and copy its REST URL + token.
3. Copy `.env.example` to `.env` and fill in `DATABASE_URL` / `DATABASE_URL_ASYNC` and `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`.
4. Restart the backend — tables are created automatically on startup.

---

## Optional: Production Deployment

For deploying to the internet (not just local use):

### Backend (Railway, Render, Fly.io, etc.)

A `Dockerfile` and `railway.json` are included. Set these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `FRONTEND_URL` | Your frontend URL (for CORS) | `https://your-app.vercel.app` |
| `CUSTOM_DOMAIN` | Custom domain if applicable | `https://your-domain.com` |
| `DATABASE_URL` | Neon Postgres connection string | `postgresql://user:pass@ep-xxx-pooler.aws.neon.tech/neondb?sslmode=require` |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST endpoint (optional) | `https://xxx.upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token (optional) | `AXXXaa...` |

### Frontend (Vercel, Netlify, etc.)

Set this build-time environment variable:

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Your backend URL | `https://your-backend.up.railway.app` |

The frontend is a standard Vite/React app. Build with `npm run build` in the `frontend/` directory.

---

## Architecture

```
Mapster/
├── pyproject.toml             # Project metadata + dependencies (uv)
├── uv.lock                    # Locked dependency versions
├── mise.toml                  # Tool versions + dev tasks
├── .python-version            # Python version pin (read by mise + uv)
├── src/mapster/                # Backend package
│   ├── app.py                 # FastAPI app factory
│   ├── main.py                # Entrypoint
│   ├── config.py              # Settings (pydantic-settings)
│   ├── db.py                  # Neon Postgres engine/session
│   ├── models.py              # SQLAlchemy models (Poster, MapCache, GenerationJob)
│   ├── services/              # Business logic (poster, cache, history, jobs)
│   └── routers/               # API routes
├── create_map_poster.py       # Map generation engine (storage-agnostic)
├── Dockerfile                 # Docker build (uses uv)
├── railway.json               # Railway deployment config
├── .env.example               # Environment variable template
├── themes/                    # 18 theme JSON files
├── fonts/                     # Custom fonts for poster text
├── data/                      # Natural Earth ocean shapefile
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main application
│   │   ├── config.js          # API URL configuration
│   │   └── components/
│   └── package.json
├── posters/                   # Generated output (auto-created)
└── cache/                     # Local disk cache (auto-created)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/start-preview` | Start async preview generation |
| POST | `/start-generate` | Start async high-res poster generation |
| POST | `/start-restore` | Restore a map from history |
| GET | `/job-status/{id}` | Poll job progress |
| GET | `/themes` | List available themes |
| GET | `/history` | List saved previews |
| DELETE | `/history/{filename}` | Delete a history entry |
| POST | `/purge-cache` | Clear all caches (local disk + Neon) |

### Data Pipeline

1. **Geocode** city name to coordinates (Nominatim)
2. **Fetch** roads, water, parks, ocean data in parallel (OSMnx/Overpass API)
3. **Process** ocean coastlines via polygonization, subtract ocean from parks
4. **Transform** geometries to SVG paths using vectorized NumPy operations
5. **Render** preview as JSON with SVG path data (frontend renders via React SVG)
6. **Generate** high-res PNG via Matplotlib at 300 DPI (on demand)
7. **Cache** at both raw data (local disk) and rendered output levels (local disk + Neon Postgres)

---

## Available Themes

Autumn, Blueprint, Contrast Zones, Copper Patina, Crimson Noir, Feature Based, Forest, Gradient Roads, Japanese Ink, Midnight Blue, Monochrome Blue, Neon Cyberpunk, Noir, Ocean, Pastel Dream, Sunset, Terracotta, Warm Beige

---

## Contributing

This project is open source and community-driven. Contributions are welcome!

- **Pull requests**: Fork the repo, make your changes, and submit a PR
- **Theme contributions**: Add a new JSON file to `themes/` following the existing format

---

## Project History

This project began as a Python CLI script by [Ankur Gupta](https://github.com/originalankur/maptoposter) and has been rebuilt into a full-stack web application.

| | Original | Mapster |
|--|----------|------------|
| **Interface** | CLI | Web app |
| **Preview** | None | Real-time SVG |
| **Formats** | 1 | 4 |
| **Themes** | 1 | 18 |
| **Caching** | None | Two-level, Neon-backed |

---

## Acknowledgments

Built upon foundational work by **[Ankur Gupta](https://github.com/originalankur/maptoposter)** who created the original map poster generation script.

Created by **[Scotty Salvo](https://x.com/MartinDAVILA)**.

Map data from [OpenStreetMap](https://www.openstreetmap.org/) contributors.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

If you find this project useful, consider buying me a coffee:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/P5P51SSYA9)
