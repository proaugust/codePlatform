from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.generate import GenerateRequest, GenerateResponse, StatusResponse
from backend.services.codegen import CodegenError, generate_project, project_status

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("/{lang}", response_model=GenerateResponse)
async def generate(lang: str, body: GenerateRequest = GenerateRequest()) -> GenerateResponse:
    try:
        result = await generate_project(lang, body.spec, use_docs=body.use_docs)
    except CodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return GenerateResponse(**result)


@router.get("/{lang}/status", response_model=StatusResponse)
async def status(lang: str) -> StatusResponse:
    try:
        result = project_status(lang)
    except CodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StatusResponse(**result)
