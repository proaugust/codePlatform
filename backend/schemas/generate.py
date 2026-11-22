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


class RunStepItem(BaseModel):
    state: str
    at: str | None = None
    message: str | None = None
    repair_attempt: int | None = None


class RunStatusResponse(BaseModel):
    lang: str
    state: str
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None
    message: str | None = None
    repair_attempt: int | None = None
    steps: list[RunStepItem] = Field(default_factory=list)
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
    mode: str | None = None


class ElicitConclusion(BaseModel):
    summary: str = ""
    goals: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    nfr: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ElicitLastPlan(BaseModel):
    summary: str = ""
    task_count: int = 0
    at: str | None = None


class ElicitationState(BaseModel):
    session_id: str
    lang: str
    status: str
    messages: list[ElicitMessage] = Field(default_factory=list)
    conclusion: ElicitConclusion | None = None
    rolling_summary: str = ""
    plan_ready: bool = False
    last_plan: ElicitLastPlan | None = None
    created_at: str | None = None
    updated_at: str | None = None
    confirmed_at: str | None = None
    closed_at: str | None = None


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


class ElicitPlanBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")
    content: str | None = Field(default=None, description="可选：一并写入的用户说明")
    conclusion: ElicitConclusion | None = Field(
        default=None, description="可选：前端编辑后的结论"
    )


class ElicitExecuteBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


class ElicitRestoreBody(BaseModel):
    target: str = Field(..., description="生成目标：java | go")


class ElicitMessageResponse(BaseModel):
    elicitation: ElicitationState
    reply: str
    ready_to_conclude: bool = False
    ready_to_plan: bool = False
    user_turns: int = 0
    max_turns: int = 20
    session_closed: bool = False


class ElicitStateResponse(BaseModel):
    elicitation: ElicitationState


class ElicitConfirmResponse(BaseModel):
    elicitation: ElicitationState
    analyze: AnalyzeResponse


class ElicitPlanResponse(BaseModel):
    elicitation: ElicitationState
    analyze: AnalyzeResponse
    plan_ready: bool = False
    session_closed: bool = False


class ElicitExecuteResponse(BaseModel):
    elicitation: ElicitationState
    generate: GenerateResponse


class ElicitSessionItem(BaseModel):
    session_id: str
    status: str | None = None
    updated_at: str | None = None
    confirmed_at: str | None = None
    summary: str = ""
    message_count: int = 0
    plan_ready: bool = False


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


class RuntimeStopResponse(BaseModel):
    ok: bool
    lang: str
    kind: str
    port: int
    killed: list[int] = Field(default_factory=list)
    listening: bool = False
    url: str = ""
    message: str = ""


class AgentLangMeta(BaseModel):
    lang: str
    backend_port: int
    frontend_port: int | None = None
    has_frontend: bool = False


class AgentMetaResponse(BaseModel):
    default_lang: str
    langs: list[AgentLangMeta]


class PlatformSettingsResponse(BaseModel):
    max_turns: int = 20
    min_max_turns: int = 3
    max_max_turns: int = 50
    tree_indent_ch: int = 2
    min_tree_indent_ch: int = 1
    max_tree_indent_ch: int = 8
    llm_base_url: str = ""
    llm_model: str = ""
    has_llm_api_key: bool = False
    llm_api_key_masked: str = ""
    auto_code_root: str = ""
    default_lang: str = "java"


class PlatformSettingsUpdateBody(BaseModel):
    max_turns: int | None = Field(default=None, ge=3, le=50, description="单会话用户发言上限（达限自动总结关闭）")
    tree_indent_ch: int | None = Field(default=None, ge=1, le=8, description="产物文件树每层缩进字符宽")
    llm_base_url: str | None = Field(default=None, description="LLM Base URL；空串清除后回退 .env")
    llm_api_key: str | None = Field(default=None, description="省略/null 不改；空串清除；非空则写入")
    llm_model: str | None = Field(default=None, description="模型名；空串清除后回退 .env")


class ProjectTreeNode(BaseModel):
    name: str
    path: str
    type: str
    children: list["ProjectTreeNode"] | None = None


class ProjectTreeResponse(BaseModel):
    lang: str
    root: str
    tree: list[ProjectTreeNode] = Field(default_factory=list)


class ProjectFileResponse(BaseModel):
    lang: str
    path: str
    content: str
    size: int
    truncated: bool = False


class ElicitDeleteResponse(BaseModel):
    lang: str
    session_id: str
    deleted: bool = True
