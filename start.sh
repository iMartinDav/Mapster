#!/bin/bash
mkdir -p /data/posters/thumbnails
mkdir -p /data/cache

# Symlink so hardcoded paths work
ln -sfn /data/posters /app/posters
ln -sfn /data/cache /app/cache

exec uv run python -m mapster.main
