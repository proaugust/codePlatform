from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.schemas.generate import (
    AnalyzeResponse,
    DocsResponse,
    ElicitConclusion,
    ElicitConfirmBody,
    ElicitConfirmResponse,
    ElicitationState,
    ElicitMessageBody,
    ElicitMessageResponse,
    ElicitRestoreBody,
    ElicitSessionsResponse,
    ElicitStateResponse,
    ElicitTargetBody,
    FrontendStartResponse,
    GenerateResponse,
    RestartResponse,
    RuntimeLogResponse,
    RunStatusResponse,
    StatusResponse,
)
from backend.services.agents.elicitor import (
    ElicitorError,
    conclude as elicit_conclude,
    confirm as elicit_confirm,
    get_or_create_elicitation,
    list_history,
    new_session as elicit_new_session,
    restore_session as elicit_restore_session,
    send_message as elicit_send_message,
)
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs
from backend.services.codegen import SUPPORTED_LANGS, CodegenError, project_status
from backend.services.frontend_codegen import FrontendCodegenError, start_frontend_dev
from backend.services.orchestrator import OrchestratorError, confirm_plan, get_run_status, run_generate
from backend.services.runtime import ProjectRuntimeError, read_runtime_log, restart_project

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


def _to_elicitation_state(data: dict[str, Any]) -> ElicitationState:
    conclusion = data.get("conclusion")
    return ElicitationState(
        session_id=str(data.get("session_id") or ""),
        lang=str(data.get("lang") or ""),
        status=str(data.get("status") or "drafting"),
        messages=list(data.get("messages") or []),
        conclusion=ElicitConclusion(**conclusion) if isinstance(conclusion, dict) else None,
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        confirmed_at=data.get("confirmed_at"),
    )


@router.post("/elicit/message", response_model=ElicitMessageResponse)
async def elicit_message(body: ElicitMessageBody) -> ElicitMessageResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_send_message(target, body.content)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitMessageResponse(
        elicitation=_to_elicitation_state(result["elicitation"]),
        reply=str(result.get("reply") or ""),
        ready_to_conclude=bool(result.get("ready_to_conclude")),
        user_turns=int(result.get("user_turns") or 0),
        max_turns=int(result.get("max_turns") or 12),
    )


@router.post("/elicit/conclude", response_model=ElicitStateResponse)
async def elicit_conclude_route(body: ElicitTargetBody) -> ElicitStateResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_conclude(target)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitStateResponse(elicitation=_to_elicitation_state(result["elicitation"]))


@router.post("/elicit/confirm", response_model=ElicitConfirmResponse)
async def elicit_confirm_route(body: ElicitConfirmBody) -> ElicitConfirmResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_confirm(
            target,
            body.conclusion.model_dump() if body.conclusion else None,
        )
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    analyze = result["analyze"]
    return ElicitConfirmResponse(
        elicitation=_to_elicitation_state(result["elicitation"]),
        analyze=AnalyzeResponse(**analyze),
    )


@router.post("/elicit/new", response_model=ElicitStateResponse)
async def elicit_new(body: ElicitTargetBody) -> ElicitStateResponse:
    target = _normalize_target(body.target)
    result = elicit_new_session(target)
    return ElicitStateResponse(elicitation=_to_elicitation_state(result["elicitation"]))


@router.post("/elicit/sessions/{session_id}/restore", response_model=ElicitStateResponse)
async def elicit_restore(session_id: str, body: ElicitRestoreBody) -> ElicitStateResponse:
    target = _normalize_target(body.target)
    try:
        result = elicit_restore_session(target, session_id)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitStateResponse(elicitation=_to_elicitation_state(result["elicitation"]))


@router.get("/{target}/elicit", response_model=ElicitStateResponse)
async def elicit_get(target: str) -> ElicitStateResponse:
    target = _normalize_target(target)
    data = get_or_create_elicitation(target)
    return ElicitStateResponse(elicitation=_to_elicitation_state(data))


@router.get("/{target}/elicit/sessions", response_model=ElicitSessionsResponse)
async def elicit_sessions(target: str) -> ElicitSessionsResponse:
    target = _normalize_target(target)
    result = list_history(target)
    return ElicitSessionsResponse(lang=result["lang"], sessions=result["sessions"])


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


class RuntimeStartBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    with_frontend: bool = Field(default=False, description="是否同时启动配套前端")


@router.post("/{target}/frontend/start", response_model=FrontendStartResponse)
async def frontend_start(target: str) -> FrontendStartResponse:
    target = _normalize_target(target)
    try:
        result = start_frontend_dev(target)
    except FrontendCodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return FrontendStartResponse(**result)


@router.post("/{target}/restart", response_model=RestartResponse)
async def project_restart(
    target: str,
    with_frontend: bool = Query(True, description="java 是否同时重启配套 Vue 前端"),
) -> RestartResponse:
    target = _normalize_target(target)
    try:
        result = restart_project(target, with_frontend=with_frontend)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RestartResponse(**result)


@router.post("/runtime/start-backend", response_model=RestartResponse)
async def runtime_start_backend(body: RuntimeStartBody) -> RestartResponse:
    """稳定入口：启动已生成后端（避免旧进程未加载 /{target}/restart）。"""
    target = _normalize_target(body.target)
    try:
        result = restart_project(target, with_frontend=body.with_frontend)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RestartResponse(**result)


@router.get("/{target}/runtime/logs", response_model=RuntimeLogResponse)
async def runtime_logs(
    target: str,
    kind: str = Query("backend", description="backend | frontend"),
) -> RuntimeLogResponse:
    target = _normalize_target(target)
    try:
        result = read_runtime_log(target, kind)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RuntimeLogResponse(**result)
