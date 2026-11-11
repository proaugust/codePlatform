from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "hello from codePlatform"}
