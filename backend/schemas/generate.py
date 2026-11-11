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
