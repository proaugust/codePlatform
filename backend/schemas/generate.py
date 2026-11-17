from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    spec: str = Field(..., min_length=1, description="用户原始需求")
    lang: str = Field(default="java", description="目标语言，默认 java")


class DocFile(BaseModel):
    key: str
    title: str
    path: str
    content: str


class AnalyzeResponse(BaseModel):
    lang: str
    docs_root: str
    files: list[DocFile]
    run_state: str | None = None
    plan_approved: bool | None = None
    plan_summary: str | None = None
    task_count: int | None = None


class DocsResponse(BaseModel):
    lang: str
    docs_root: str
    exists: bool
    files: list[DocFile]


class GenerateRequest(BaseModel):
    spec: str | None = Field(default=None, description="可选补充说明；优先使用 docs/ 四件套")
    use_docs: bool = Field(default=True, description="是否读取 docs/（含 05-structure 与需求四件套）")


class EndpointInfo(BaseModel):
    method: str
    path: str
    description: str = ""


class GenerateResponse(BaseModel):
    lang: str
    port: int
    root: str
    files: list[str]
    endpoints: list[EndpointInfo]
    used_docs: bool = False
    run_state: str | None = None
    validation_ok: bool | None = None
    repair_count: int | None = None
    frontend_ok: bool | None = None
    frontend_skipped: bool | None = None
    frontend_port: int | None = None
    frontend_root: str | None = None
    frontend_files: list[str] = Field(default_factory=list)
    frontend_error: str | None = None


class RunStatusResponse(BaseModel):
    lang: str
    state: str
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None
    auto_approve_plan: bool = True
    plan_approved: bool = False
    plan_summary: str | None = None
    task_count: int = 0
    validation_ok: bool | None = None
    repair_count: int = 0
    ir_dir: str | None = None


class StatusResponse(BaseModel):
    lang: str
    port: int
    root: str
    exists: bool
    has_spec: bool
    has_docs: bool = False
    docs_root: str | None = None
    doc_files: list[str] = Field(default_factory=list)
    file_count: int
    proxy_prefix: str
    suggested_tests: list[dict[str, str]]
    frontend_exists: bool = False
    frontend_root: str | None = None
    frontend_port: int | None = None


class ElicitMessage(BaseModel):
    role: str
    content: str
    at: str | None = None


class ElicitConclusion(BaseModel):
    summary: str = ""
    goals: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    nfr: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ElicitationState(BaseModel):
    session_id: str
    lang: str
    status: str
    messages: list[ElicitMessage] = Field(default_factory=list)
    conclusion: ElicitConclusion | None = None
    created_at: str | None = None
    updated_at: str | None = None
    confirmed_at: str | None = None


class ElicitMessageBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    content: str = Field(..., min_length=1, description="用户澄清消息")


class ElicitTargetBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


class ElicitConfirmBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    conclusion: ElicitConclusion | None = Field(
        default=None, description="可选：确认前编辑后的结论"
    )


class ElicitRestoreBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


class ElicitMessageResponse(BaseModel):
    elicitation: ElicitationState
    reply: str
    ready_to_conclude: bool = False
    user_turns: int = 0
    max_turns: int = 12


class ElicitStateResponse(BaseModel):
    elicitation: ElicitationState


class ElicitConfirmResponse(BaseModel):
    elicitation: ElicitationState
    analyze: AnalyzeResponse


class ElicitSessionItem(BaseModel):
    session_id: str
    status: str | None = None
    updated_at: str | None = None
    confirmed_at: str | None = None
    summary: str = ""
    message_count: int = 0


class ElicitSessionsResponse(BaseModel):
    lang: str
    sessions: list[ElicitSessionItem] = Field(default_factory=list)


class FrontendStartResponse(BaseModel):
    ok: bool
    started: bool = False
    already_running: bool = False
    lang: str
    port: int
    url: str
    bat: str | None = None
    message: str = ""


class RestartResponse(BaseModel):
    ok: bool
    lang: str
    message: str = ""
    backend: dict = Field(default_factory=dict)
    frontend: dict | None = None


class RuntimeLogResponse(BaseModel):
    lang: str
    kind: str
    path: str
    exists: bool = False
    listening: bool = False
    port: int
    url: str
    text: str = ""
    updated_at: str = ""
