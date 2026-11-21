from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from backend.core.config import LANG_PORTS, settings
from backend.services.analyze import AnalyzeError, load_docs_as_spec, read_docs
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = frozenset({"java", "go"})
# 后端重生成时保留：需求文档、业务前端（含 node_modules）、日志与构建产物，避免 WinError 5 锁文件拖垮整次执行
PRESERVE_ON_GENERATE = frozenset({"docs", "frontend", "logs", "target", ".git"})


class CodegenError(RuntimeError):
    pass


def _system_prompt(lang: str, port: int) -> str:
    if lang == "java":
        stack = (
            "Generate a complete runnable Spring Boot 3.x Maven backend (Java 21). "
            "pom.xml MUST set <java.version>21</java.version>. "
            "Must include pom.xml, application.yml (or application.properties), "
            "main Application class, entities/repositories if DB tables exist, and REST controllers. "
            f"Server port MUST be {port}. Enable CORS for "
            "http://localhost:5173, http://127.0.0.1:5173, "
            "http://localhost:5174, http://127.0.0.1:5174, "
            "http://localhost:5175, http://127.0.0.1:5175. "
            "Package root: com.example.autocode. "
            "Prefer H2 in-memory for local demo unless docs require otherwise."
        )
    else:
        stack = (
            "Generate a complete runnable Go backend using ONLY the Go standard library (net/http). "
            "Must include go.mod (module example.com/autocode), main.go, and handlers. "
            f"Listen on :{port}. Enable CORS for "
            "http://localhost:5173, http://127.0.0.1:5173, "
            "http://localhost:5174, http://127.0.0.1:5174, "
            "http://localhost:5175, http://127.0.0.1:5175. "
            "No third-party web frameworks."
        )

    return (
        "You are a code generation engine. Output a single JSON object only, no markdown. "
        "Schema:\n"
        "{\n"
        '  "files": [{"path": "relative/path", "content": "file content"}],\n'
        '  "endpoints": [{"method": "GET", "path": "/health", "description": "..."}]\n'
        "}\n"
        "Rules:\n"
        "- Always include GET /health returning JSON {\"status\":\"ok\"}. Prefer also mapping GET / to the same health payload.\n"
        "- If a GlobalExceptionHandler / @RestControllerAdvice catch-all exists, do NOT map NoResourceFoundException / NoHandlerFoundException to 500; return 404 instead.\n"
        "- Always include src/main/resources/static/favicon.ico (minimal valid ICO is fine) so browser /favicon.ico does not hit NoResourceFoundException.\n"
        "- Implement APIs and data model described in the provided requirement docs and Change Plan.\n"
        "- If Change Plan / docs list DELETE (or other) endpoints, they MUST exist in controllers and endpoints[].\n"
        "- If an existing domain (e.g. Book) is already in the project/docs, prefer extending it; do not replace with an unrelated greenfield system.\n"
        "- Do NOT write files under docs/ or frontend/.\n"
        "- paths must be relative, use forward slashes, no .. or absolute paths.\n"
        "- content must be full file source, not placeholders like TODO implement later.\n"
        f"- {stack}\n"
    )


def _safe_rel_path(raw: str) -> Path:
    rel = raw.replace("\\", "/").strip().lstrip("/")
    if not rel or rel.startswith("..") or "/../" in f"/{rel}/":
        raise CodegenError(f"非法文件路径: {raw!r}")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        raise CodegenError(f"非法文件路径: {raw!r}")
    if path.parts and path.parts[0].lower() == "docs":
        raise CodegenError("禁止覆盖 docs/ 需求文档")
    if path.parts and path.parts[0].lower() == "frontend":
        raise CodegenError("禁止在后端生成中写入 frontend/（由前端生成管线负责）")
    return path


def _rmtree_retry(path: Path, *, attempts: int = 4) -> None:
    import time

    last: OSError | None = None
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except OSError as e:
            last = e
            time.sleep(0.4 * (i + 1))
    assert last is not None
    raise CodegenError(f"无法删除目录 {path}: {last}") from last


def _clear_dir(path: Path, *, preserve: frozenset[str] = PRESERVE_ON_GENERATE) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.name in preserve:
            continue
        if child.is_dir():
            _rmtree_retry(child)
        else:
            try:
                child.unlink()
            except OSError as e:
                raise CodegenError(f"无法删除文件 {child}: {e}") from e


def _write_files(root: Path, files: list[dict[str, Any]]) -> list[str]:
    written: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        content = item.get("content")
        if not isinstance(raw_path, str) or not isinstance(content, str):
            continue
        rel = _safe_rel_path(raw_path)
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        written.append(rel.as_posix())
    if not written:
        raise CodegenError("LLM 未返回任何有效文件")
    return written


async def generate_project(lang: str, spec: str | None = None, *, use_docs: bool = True) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise CodegenError(f"不支持的语言: {lang}")

    port = LANG_PORTS[lang]
    root = settings.auto_code_dir(lang)
    root.mkdir(parents=True, exist_ok=True)

    doc_spec = ""
    if use_docs:
        try:
            doc_spec = load_docs_as_spec(lang)
        except AnalyzeError:
            doc_spec = ""

    raw_spec = (spec or "").strip()
    if doc_spec:
        final_spec = doc_spec
        if raw_spec:
            final_spec = doc_spec + "\n\n---\n\n# 用户补充\n\n" + raw_spec + "\n"
    else:
        if not raw_spec:
            raise CodegenError("请先分析需求生成 docs/，或直接提供 spec")
        final_spec = raw_spec

    try:
        raw = await chat_completion(
            system=_system_prompt(lang, port),
            user=f"Language: {lang}\nPort: {port}\n\nRequirement documents:\n{final_spec}",
        )
    except LlmError as e:
        raise CodegenError(str(e)) from e

    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise CodegenError(str(e)) from e

    files = data.get("files")
    if not isinstance(files, list):
        raise CodegenError("JSON 缺少 files 数组")

    endpoints_raw = data.get("endpoints") or []
    endpoints: list[dict[str, str]] = []
    if isinstance(endpoints_raw, list):
        for ep in endpoints_raw:
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method") or "GET").upper()
            path = str(ep.get("path") or "").strip()
            desc = str(ep.get("description") or "").strip()
            if path:
                endpoints.append({"method": method, "path": path, "description": desc})

    _clear_dir(root)
    written = _write_files(root, files)
    if raw_spec and not doc_spec:
        (root / "SPEC.md").write_text(raw_spec + "\n", encoding="utf-8", newline="\n")

    logger.info("生成完成 lang=%s files=%d port=%s", lang, len(written), port)
    return {
        "lang": lang,
        "port": port,
        "root": str(root),
        "files": written,
        "endpoints": endpoints,
        "used_docs": bool(doc_spec),
    }


def project_status(lang: str) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise CodegenError(f"不支持的语言: {lang}")
    root = settings.auto_code_dir(lang)
    port = LANG_PORTS[lang]
    docs = read_docs(lang)
    exists = root.is_dir() and any(p.name != "docs" for p in root.iterdir()) if root.is_dir() else False
    has_spec = (root / "SPEC.md").is_file()
    file_count = 0
    if root.is_dir():
        file_count = sum(1 for p in root.rglob("*") if p.is_file())
    from backend.services.frontend_codegen import FRONTEND_PORT, frontend_root

    fe_root = frontend_root(lang)
    fe_exists = fe_root.is_dir() and any(fe_root.iterdir())
    return {
        "lang": lang,
        "port": port,
        "root": str(root),
        "exists": exists,
        "has_spec": has_spec,
        "has_docs": bool(docs.get("exists")),
        "docs_root": docs.get("docs_root"),
        "doc_files": [f["path"] for f in docs.get("files", [])],
        "file_count": file_count,
        "proxy_prefix": f"/{lang}-api",
        "suggested_tests": [
            {"method": "GET", "path": "/health", "url": f"/{lang}-api/health"},
        ],
        "frontend_exists": fe_exists,
        "frontend_root": str(fe_root) if fe_exists else None,
        "frontend_port": FRONTEND_PORT if fe_exists else None,
    }
