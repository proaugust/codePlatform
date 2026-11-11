from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.schemas.generate import (
    AnalyzeResponse,
    DocsResponse,
    GenerateResponse,
    RunStatusResponse,
    StatusResponse,
)
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs
from backend.services.codegen import SUPPORTED_LANGS, CodegenError, project_status
from backend.services.orchestrator import OrchestratorError, confirm_plan, get_run_status, run_generate

router = APIRouter(prefix="/agent", tags=["agent"])


class AnalyzeBody(BaseModel):
    spec: str = Field(..., min_length=1, description="用户原始需求")
    target: str = Field(..., description="生成目标：java | go")


class GenerateBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    spec: str | None = Field(default=None, description="可选补充说明")
    use_docs: bool = Field(default=True, description="是否使用已分析的 docs/")


class PlanConfirmBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


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


@router.post("/plan/confirm", response_model=RunStatusResponse)
async def plan_confirm(body: PlanConfirmBody) -> RunStatusResponse:
    target = _normalize_target(body.target)
    try:
        result = confirm_plan(target)
    except OrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RunStatusResponse(
        lang=result["lang"],
        state=result["state"],
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        error=result.get("error"),
        auto_approve_plan=bool(result.get("auto_approve_plan")),
        plan_approved=bool(result.get("plan_approved")),
        plan_summary=result.get("plan_summary"),
        task_count=int(result.get("task_count") or 0),
        validation_ok=result.get("validation_ok"),
        repair_count=int(result.get("repair_count") or 0),
        ir_dir=result.get("ir_dir"),
    )


@router.get("/{target}/run", response_model=RunStatusResponse)
async def run_status(target: str) -> RunStatusResponse:
    target = _normalize_target(target)
    try:
        result = get_run_status(target)
    except OrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RunStatusResponse(
        lang=result["lang"],
        state=result["state"],
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
        error=result.get("error"),
        auto_approve_plan=bool(result.get("auto_approve_plan")),
        plan_approved=bool(result.get("plan_approved")),
        plan_summary=result.get("plan_summary"),
        task_count=int(result.get("task_count") or 0),
        validation_ok=result.get("validation_ok"),
        repair_count=int(result.get("repair_count") or 0),
        ir_dir=result.get("ir_dir"),
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateBody) -> GenerateResponse:
    target = _normalize_target(body.target)
    try:
        result = await run_generate(target, body.spec, use_docs=body.use_docs)
    except OrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
