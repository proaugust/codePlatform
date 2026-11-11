from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.generate import AnalyzeRequest, AnalyzeResponse, DocsResponse
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = await analyze_requirements(body.lang, body.spec)
    except AnalyzeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AnalyzeResponse(**result)


@router.get("/{lang}/docs", response_model=DocsResponse)
async def get_docs(lang: str) -> DocsResponse:
    try:
        result = read_docs(lang)
    except AnalyzeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return DocsResponse(**result)
