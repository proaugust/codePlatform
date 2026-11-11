from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.schemas.generate import AnalyzeResponse, DocsResponse, GenerateResponse, StatusResponse
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs
from backend.services.codegen import SUPPORTED_LANGS, CodegenError, generate_project, project_status

router = APIRouter(prefix="/agent", tags=["agent"])


class AnalyzeBody(BaseModel):
    spec: str = Field(..., min_length=1, description="用户原始需求")
    target: str = Field(..., description="生成目标：java | go")


class GenerateBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    spec: str | None = Field(default=None, description="可选补充说明")
    use_docs: bool = Field(default=True, description="是否使用已分析的 docs/")


def _normalize_target(target: str) -> str:
    t = target.lower().strip()
    if t not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail=f"不支持的 target: {target}，可选: java, go")
    return t


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeBody) -> AnalyzeResponse:
    target = _normalize_target(body.target)
    try:
        result = await analyze_requirements(target, body.spec)
    except AnalyzeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AnalyzeResponse(**result)


@router.get("/{target}/docs", response_model=DocsResponse)
async def docs(target: str) -> DocsResponse:
    target = _normalize_target(target)
    try:
        result = read_docs(target)
    except AnalyzeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return DocsResponse(**result)


@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateBody) -> GenerateResponse:
    target = _normalize_target(body.target)
    try:
        result = await generate_project(target, body.spec, use_docs=body.use_docs)
    except CodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return GenerateResponse(**result)


@router.get("/{target}/status", response_model=StatusResponse)
async def status(target: str) -> StatusResponse:
    target = _normalize_target(target)
    try:
        result = project_status(target)
    except CodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StatusResponse(**result)
