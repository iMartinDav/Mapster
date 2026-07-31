FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies for geospatial libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Make src/ importable so `python -m mapster.main` works
ENV PYTHONPATH=/app/src

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy package source
COPY src/ ./src/

# Copy domain code (used by services/poster.py)
COPY create_map_poster.py .
COPY generate_previews.py .

# Copy static assets
COPY themes/ ./themes/
COPY fonts/ ./fonts/
COPY data/ ./data/

# Local dirs are ephemeral (lost on redeploy) — durable history/cache live in
# Neon Postgres, job state in Upstash Redis; these are just scratch space.
RUN mkdir -p posters cache posters/thumbnails

CMD ["uv", "run", "python", "-m", "mapster.main"]
