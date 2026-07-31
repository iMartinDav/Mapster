"""Admin routes (purge-cache)."""

import os

from fastapi import APIRouter, HTTPException, Query

from mapster.services import poster

router = APIRouter(tags=["admin"])


@router.post("/purge-cache")
async def purge_cache(admin_key: str = Query(default="")):
    expected_key = os.environ.get("ADMIN_KEY", "")
    if expected_key and admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")

    results = poster.purge_all_cache()

    return {"status": "purged", "details": results}
