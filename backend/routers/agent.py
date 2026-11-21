from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.config import LANG_PORTS, settings
from backend.schemas.generate import (
    AgentLangMeta,
    AgentMetaResponse,
    AnalyzeResponse,
    DocsResponse,
    ElicitConclusion,
    ElicitConfirmBody,
    ElicitConfirmResponse,
    ElicitDeleteResponse,
    ElicitExecuteBody,
    ElicitExecuteResponse,
    ElicitationState,
    ElicitLastPlan,
    ElicitMessageBody,
    ElicitMessageResponse,
    ElicitPlanBody,
    ElicitPlanResponse,
    ElicitRestoreBody,
    ElicitSessionsResponse,
    ElicitStateResponse,
    ElicitTargetBody,
    FrontendStartResponse,
    GenerateResponse,
    PlatformSettingsResponse,
    PlatformSettingsUpdateBody,
    ProjectFileResponse,
    ProjectTreeNode,
    ProjectTreeResponse,
    RestartResponse,
    RuntimeLogResponse,
    RuntimeStopResponse,
    RunStatusResponse,
    StatusResponse,
)
from backend.services.agents.elicitor import (
    ElicitorError,
    close_current_session as elicit_close_session,
    conclude as elicit_conclude,
    confirm as elicit_confirm,
    delete_history_session as elicit_delete_session,
    get_or_create_elicitation,
    list_history,
    new_session as elicit_new_session,
    restore_session as elicit_restore_session,
    run_execute as elicit_run_execute,
    run_plan as elicit_run_plan,
    send_message as elicit_send_message,
)
from backend.services.analyze import AnalyzeError, analyze_requirements, read_docs
from backend.services.codegen import SUPPORTED_LANGS, CodegenError, project_status
from backend.services.frontend_codegen import FRONTEND_PORT, FrontendCodegenError, start_frontend_dev
from backend.services.orchestrator import OrchestratorError, confirm_plan, get_run_status, run_generate
from backend.services.platform_prefs import (
    MAX_MAX_TURNS,
    MAX_TREE_INDENT_CH,
    MIN_MAX_TURNS,
    MIN_TREE_INDENT_CH,
    get_max_turns,
    mask_api_key,
    read_prefs,
    resolve_llm_config,
    write_prefs,
)
from backend.services.project_files import ProjectFilesError, list_tree, read_file as read_project_file
from backend.services.runtime import (
    ProjectRuntimeError,
    clear_runtime_log,
    read_runtime_log,
    restart_project,
    stop_backend,
    stop_frontend,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# java / go 产物均可配套 Vue 前端
_LANGS_WITH_FRONTEND = frozenset({"java", "go"})


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


@router.get("/meta", response_model=AgentMetaResponse)
async def agent_meta() -> AgentMetaResponse:
    langs = [
        AgentLangMeta(
            lang=lang,
            backend_port=port,
            frontend_port=FRONTEND_PORT if lang in _LANGS_WITH_FRONTEND else None,
            has_frontend=lang in _LANGS_WITH_FRONTEND,
        )
        for lang, port in LANG_PORTS.items()
    ]
    return AgentMetaResponse(default_lang=settings.default_lang, langs=langs)


def _settings_response(prefs: dict) -> PlatformSettingsResponse:
    llm = resolve_llm_config()
    return PlatformSettingsResponse(
        max_turns=int(prefs["max_turns"]),
        min_max_turns=MIN_MAX_TURNS,
        max_max_turns=MAX_MAX_TURNS,
        tree_indent_ch=int(prefs["tree_indent_ch"]),
        min_tree_indent_ch=MIN_TREE_INDENT_CH,
        max_tree_indent_ch=MAX_TREE_INDENT_CH,
        llm_base_url=llm["llm_base_url"],
        llm_model=llm["llm_model"],
        has_llm_api_key=bool(llm["llm_api_key"]),
        llm_api_key_masked=mask_api_key(llm["llm_api_key"]),
        auto_code_root=str(settings.auto_code_root),
        default_lang=settings.default_lang,
    )


@router.get("/settings", response_model=PlatformSettingsResponse)
async def platform_settings_get() -> PlatformSettingsResponse:
    return _settings_response(read_prefs())


@router.put("/settings", response_model=PlatformSettingsResponse)
async def platform_settings_put(body: PlatformSettingsUpdateBody) -> PlatformSettingsResponse:
    prefs = write_prefs(
        {
            "max_turns": body.max_turns,
            "tree_indent_ch": body.tree_indent_ch,
            "llm_base_url": body.llm_base_url,
            "llm_api_key": body.llm_api_key,
            "llm_model": body.llm_model,
        }
    )
    return _settings_response(prefs)


def _to_elicitation_state(data: dict[str, Any]) -> ElicitationState:
    conclusion = data.get("conclusion")
    last_plan = data.get("last_plan")
    return ElicitationState(
        session_id=str(data.get("session_id") or ""),
        lang=str(data.get("lang") or ""),
        status=str(data.get("status") or "drafting"),
        messages=list(data.get("messages") or []),
        conclusion=ElicitConclusion(**conclusion) if isinstance(conclusion, dict) else None,
        rolling_summary=str(data.get("rolling_summary") or ""),
        plan_ready=bool(data.get("plan_ready")),
        last_plan=ElicitLastPlan(**last_plan) if isinstance(last_plan, dict) else None,
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        confirmed_at=data.get("confirmed_at"),
        closed_at=data.get("closed_at"),
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
        ready_to_conclude=bool(result.get("ready_to_conclude") or result.get("ready_to_plan")),
        ready_to_plan=bool(result.get("ready_to_plan") or result.get("ready_to_conclude")),
        user_turns=int(result.get("user_turns") or 0),
        max_turns=int(result.get("max_turns") or get_max_turns()),
        session_closed=bool(result.get("session_closed")),
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
    """兼容旧前端：等同分析计划（不生成代码）。"""
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


@router.post("/elicit/plan", response_model=ElicitPlanResponse)
async def elicit_plan_route(body: ElicitPlanBody) -> ElicitPlanResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_run_plan(
            target,
            content=body.content,
            conclusion=body.conclusion.model_dump() if body.conclusion else None,
        )
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitPlanResponse(
        elicitation=_to_elicitation_state(result["elicitation"]),
        analyze=AnalyzeResponse(**result["analyze"]),
        plan_ready=bool(result.get("plan_ready")),
        session_closed=bool(result.get("session_closed")),
    )


@router.post("/elicit/execute", response_model=ElicitExecuteResponse)
async def elicit_execute_route(body: ElicitExecuteBody) -> ElicitExecuteResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_run_execute(target)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitExecuteResponse(
        elicitation=_to_elicitation_state(result["elicitation"]),
        generate=GenerateResponse(**result["generate"]),
    )


@router.post("/elicit/new", response_model=ElicitStateResponse)
async def elicit_new(body: ElicitTargetBody) -> ElicitStateResponse:
    target = _normalize_target(body.target)
    result = await elicit_new_session(target)
    return ElicitStateResponse(elicitation=_to_elicitation_state(result["elicitation"]))


@router.post("/elicit/close", response_model=ElicitStateResponse)
async def elicit_close(body: ElicitTargetBody) -> ElicitStateResponse:
    target = _normalize_target(body.target)
    try:
        result = await elicit_close_session(target)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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


@router.delete("/{target}/elicit/sessions/{session_id}", response_model=ElicitDeleteResponse)
async def elicit_delete_session_route(target: str, session_id: str) -> ElicitDeleteResponse:
    target = _normalize_target(target)
    try:
        result = elicit_delete_session(target, session_id)
    except ElicitorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ElicitDeleteResponse(**result)


@router.get("/{target}/tree", response_model=ProjectTreeResponse)
async def project_tree(target: str) -> ProjectTreeResponse:
    target = _normalize_target(target)
    try:
        result = list_tree(target)
    except ProjectFilesError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ProjectTreeResponse(
        lang=result["lang"],
        root=result["root"],
        tree=[ProjectTreeNode.model_validate(n) for n in result["tree"]],
    )


@router.get("/{target}/file", response_model=ProjectFileResponse)
async def project_file(
    target: str,
    path: str = Query(..., min_length=1, description="相对 auto_code/{lang} 的路径"),
) -> ProjectFileResponse:
    target = _normalize_target(target)
    try:
        result = read_project_file(target, path)
    except ProjectFilesError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ProjectFileResponse(**result)


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


class RuntimeStopBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


@router.post("/{target}/frontend/start", response_model=FrontendStartResponse)
async def frontend_start(target: str) -> FrontendStartResponse:
    target = _normalize_target(target)
    try:
        result = start_frontend_dev(target)
    except FrontendCodegenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not result.get("ok", False):
        raise HTTPException(status_code=400, detail=str(result.get("message") or "前端启动失败"))
    return FrontendStartResponse(**result)


@router.post("/{target}/frontend/stop", response_model=RuntimeStopResponse)
async def frontend_stop(target: str) -> RuntimeStopResponse:
    target = _normalize_target(target)
    try:
        result = stop_frontend(target)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RuntimeStopResponse(**result)


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


@router.post("/runtime/stop-backend", response_model=RuntimeStopResponse)
async def runtime_stop_backend(body: RuntimeStopBody) -> RuntimeStopResponse:
    """稳定入口：停止已生成后端。"""
    target = _normalize_target(body.target)
    try:
        result = stop_backend(target)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RuntimeStopResponse(**result)


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


@router.delete("/{target}/runtime/logs", response_model=RuntimeLogResponse)
async def runtime_logs_clear(
    target: str,
    kind: str = Query("backend", description="backend | frontend"),
) -> RuntimeLogResponse:
    target = _normalize_target(target)
    try:
        result = clear_runtime_log(target, kind)
    except ProjectRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RuntimeLogResponse(**result)
