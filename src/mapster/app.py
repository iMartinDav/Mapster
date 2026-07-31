"""FastAPI application factory."""

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mapster.config import get_settings
from mapster.db import init_db
from mapster.routers import admin, geo, history, jobs, themes, thumbnails
from mapster.services import jobs as jobs_service


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Mapster API")

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(themes.router)
    app.include_router(jobs.router)
    app.include_router(history.router)
    app.include_router(admin.router)
    app.include_router(thumbnails.router)
    app.include_router(geo.router)

    # --- Database (Neon Postgres) ---
    init_db()

    # --- Background tasks ---
    jobs_service.start_cleanup_thread()

    # --- Static files ---
    os.makedirs("posters/thumbnails", exist_ok=True)
    app.mount("/posters", StaticFiles(directory="posters"), name="posters")
    app.mount("/fonts", StaticFiles(directory="fonts"), name="fonts")

    @app.get("/")
    def root():
        return {"message": "Mapster API"}

    return app


app = create_app()
