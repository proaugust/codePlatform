from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.schemas.generate import AnalyzeResponse, DocsResponse, GenerateResponse, StatusResponse
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs
from backend.services.codegen import CodegenError, generate_project, project_status


class SpecBody(BaseModel):
    spec: str = Field(..., min_length=1, description="用户原始需求")


class GenerateBody(BaseModel):
    spec: str | None = Field(default=None, description="可选补充说明")
    use_docs: bool = Field(default=True)


def make_lang_router(lang: str) -> APIRouter:
    """为某一语言提供独立接口前缀，如 /java、/go。"""
    router = APIRouter(prefix=f"/{lang}", tags=[lang])

    @router.post("/analyze", response_model=AnalyzeResponse)
    async def analyze(body: SpecBody) -> AnalyzeResponse:
        try:
            result = await analyze_requirements(lang, body.spec)
        except AnalyzeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return AnalyzeResponse(**result)

    @router.get("/docs", response_model=DocsResponse)
    async def docs() -> DocsResponse:
        try:
            result = read_docs(lang)
        except AnalyzeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return DocsResponse(**result)

    @router.post("/generate", response_model=GenerateResponse)
    async def generate(body: GenerateBody = GenerateBody()) -> GenerateResponse:
        try:
            result = await generate_project(lang, body.spec, use_docs=body.use_docs)
        except CodegenError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return GenerateResponse(**result)

    @router.get("/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        try:
            result = project_status(lang)
        except CodegenError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return StatusResponse(**result)

    return router


java_router = make_lang_router("java")
go_router = make_lang_router("go")
