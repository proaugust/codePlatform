from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from backend.core.config import LANG_PORTS, settings
from backend.services.analyze import AnalyzeError, load_docs_as_spec, read_docs
from backend.services.llm import LlmError, chat_completion_json

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = frozenset({"java", "go"})
# 后端重生成时保留：需求文档、业务前端（含 node_modules）、日志与构建产物，避免 WinError 5 锁文件拖垮整次执行
PRESERVE_ON_GENERATE = frozenset({"docs", "frontend", "logs", "target", ".git"})

_JAVA_FALLBACK_GLOBS = (
    "pom.xml",
    "src/main/resources/application.yml",
    "src/main/resources/application.properties",
    "src/main/java/**/*.java",
    "src/test/java/**/*.java",
)
_GO_FALLBACK_GLOBS = ("go.mod", "*.go", "**/*.go")


class CodegenError(RuntimeError):
    pass


def _project_exists(lang: str, root: Path) -> bool:
    if lang == "java":
        return (root / "pom.xml").is_file()
    return (root / "go.mod").is_file() or (root / "main.go").is_file()


def _stack_rules(lang: str, port: int) -> str:
    if lang == "java":
        return (
            "Spring Boot 3.x Maven backend (Java 21). "
            "pom.xml MUST set <java.version>21</java.version>. "
            f"Server port MUST be {port}. Enable CORS for "
            "http://localhost:5173, http://127.0.0.1:5173, "
            "http://localhost:5174, http://127.0.0.1:5174, "
            "http://localhost:5175, http://127.0.0.1:5175. "
            "Package root: com.example.autocode. "
            "Prefer H2 in-memory unless docs require otherwise. "
            "If a GlobalExceptionHandler catch-all exists, map missing routes to 404 not 500. "
            "Include src/main/resources/static/favicon.ico when touching resources."
        )
    return (
        "Go stdlib net/http only (go 1.22+ ServeMux method routes OK). "
        "module example.com/autocode. Prefer a compact single main.go implementing all routes. "
        f"Listen on 127.0.0.1:{port} only (not :{port}/0.0.0.0 — avoids Windows Firewall prompts). "
        "CORS for localhost/127.0.0.1:5173-5175. No third-party web frameworks. "
        "Keep source compact; avoid long comments."
    )


def _file_system_prompt(lang: str, port: int, *, incremental: bool) -> str:
    mode = (
        "Incremental edit: output ONLY the requested file(s). Preserve existing packages/APIs not mentioned. "
        "Extend domain (e.g. Book) rather than inventing an unrelated system."
        if incremental
        else "Greenfield batch: output complete file sources for the requested paths only."
    )
    return (
        "You are a code generation engine. Output a single JSON object only, no markdown.\n"
        "Schema:\n"
        "{\n"
        '  "files": [{"path": "relative/path", "content": "full file source"}]\n'
        "}\n"
        "Rules:\n"
        f"- {mode}\n"
        "- Always ensure GET /health returns {\"status\":\"ok\"} when touching health/entry files.\n"
        "- If Change Plan / docs list DELETE (or other) endpoints, implement them in controllers/services.\n"
        "- Do NOT write files under docs/ or frontend/.\n"
        "- paths relative, forward slashes, no .. ; content must be full source, not TODO stubs.\n"
        f"- {_stack_rules(lang, port)}\n"
        "- Return at most 3 files in this response; only the paths asked for.\n"
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


def _write_files(
    root: Path,
    files: list[dict[str, Any]],
    *,
    allow_paths: set[str] | None = None,
) -> list[str]:
    written: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        content = item.get("content")
        if not isinstance(raw_path, str) or not isinstance(content, str):
            continue
        rel = _safe_rel_path(raw_path)
        rel_s = rel.as_posix()
        if allow_paths is not None and rel_s not in allow_paths:
            # 允许大小写/前缀微调：若 allow 含同名文件则放行
            if not any(rel_s.endswith(a) or a.endswith(rel_s) for a in allow_paths):
                logger.warning("跳过非目标路径: %s", rel_s)
                continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        written.append(rel_s)
    if not written:
        raise CodegenError("LLM 未返回任何有效文件")
    return written


def _normalize_plan_path(raw: str) -> str | None:
    s = str(raw or "").replace("\\", "/").strip().lstrip("./")
    if not s or " or " in s.lower() or s.endswith("/"):
        return None
    if ".." in s or s.lower().startswith("docs/") or s.lower().startswith("frontend/"):
        return None
    # 跳过占位描述
    if " " in s and not s.endswith((".java", ".go", ".yml", ".yaml", ".xml", ".properties", ".md")):
        return None
    return s


def _plan_target_files(plan: dict[str, Any] | None) -> list[str]:
    if not plan:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for task in plan.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        for f in task.get("files") or []:
            p = _normalize_plan_path(str(f))
            if not p or p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def _fallback_existing_sources(lang: str, root: Path) -> list[str]:
    globs = _JAVA_FALLBACK_GLOBS if lang == "java" else _GO_FALLBACK_GLOBS
    found: list[str] = []
    seen: set[str] = set()
    for pattern in globs:
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel.startswith("docs/") or rel.startswith("frontend/") or rel.startswith("target/"):
                continue
            if rel in seen:
                continue
            seen.add(rel)
            found.append(rel)
    # 增量回退时优先 controller/service，避免一次改太多
    priority = [f for f in found if any(x in f for x in ("controller", "service", "Controller", "Service", "handler"))]
    rest = [f for f in found if f not in priority]
    ordered = priority + rest
    return ordered[:12]


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _endpoints_from_plan(plan: dict[str, Any] | None) -> list[dict[str, str]]:
    endpoints: list[dict[str, str]] = []
    if not plan:
        return endpoints
    for ep in plan.get("apis") or []:
        if not isinstance(ep, dict):
            continue
        method = str(ep.get("method") or "GET").upper()
        path = str(ep.get("path") or "").strip()
        desc = str(ep.get("description") or "").strip()
        if path:
            endpoints.append({"method": method, "path": path, "description": desc})
    if not any(e["path"] == "/health" for e in endpoints):
        endpoints.insert(0, {"method": "GET", "path": "/health", "description": "健康检查"})
    return endpoints


def _read_existing_snippet(root: Path, rel: str, *, max_chars: int = 6000) -> str:
    path = root / rel
    if not path.is_file():
        return "(file does not exist yet — create it)"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "(unreadable)"
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(truncated)…"
    return text


def expand_repair_paths(root: Path, paths: list[str], *, max_files: int = 6) -> list[str]:
    """报错文件 + 同目录 sibling 源文件（补 undefined helper 用），上限 max_files。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        norm = str(raw or "").replace("\\", "/").strip().lstrip("./")
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    dirs = {str(Path(p).parent).replace("\\", "/") for p in out}
    for d in sorted(dirs):
        dir_path = root if d in {".", ""} else root / d
        if not dir_path.is_dir():
            continue
        try:
            children = sorted(dir_path.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if not child.is_file():
                continue
            if child.suffix not in {".go", ".java"}:
                continue
            name = child.name
            if name.endswith("_test.go") or name.endswith("Test.java"):
                continue
            try:
                rel = child.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel in seen:
                continue
            seen.add(rel)
            out.append(rel)
            if len(out) >= max_files:
                return out[:max_files]
    return out[:max_files]


def _greenfield_batches(lang: str) -> list[list[str]]:
    if lang == "java":
        return [
            [
                "pom.xml",
                "src/main/resources/application.yml",
                "src/main/java/com/example/autocode/AutoCodeApplication.java",
            ],
            [
                "src/main/java/com/example/autocode/config/CorsConfig.java",
                "src/main/java/com/example/autocode/controller/HealthController.java",
                "src/main/java/com/example/autocode/exception/GlobalExceptionHandler.java",
            ],
            [
                "src/main/java/com/example/autocode/exception/BusinessException.java",
                "src/main/java/com/example/autocode/exception/ErrorResponse.java",
            ],
        ]
    # Go：单文件一批，整站放进 main.go，降低 JSON 转义失败概率
    return [
        ["go.mod"],
        ["main.go"],
    ]


async def _generate_file_batch(
    *,
    lang: str,
    port: int,
    root: Path,
    paths: list[str],
    final_spec: str,
    plan: dict[str, Any] | None,
    incremental: bool,
) -> list[str]:
    allow = set(paths)
    existing_bits = []
    for p in paths:
        existing_bits.append(f"### {p}\n```\n{_read_existing_snippet(root, p)}\n```")
    plan_bits = ""
    if plan:
        plan_bits = (
            f"\nChange Plan summary: {plan.get('summary')}\n"
            f"APIs: {plan.get('apis')}\n"
            f"Tasks touching these files: {[t for t in (plan.get('tasks') or []) if isinstance(t, dict)]}\n"
        )
    user = (
        f"Language: {lang}\nPort: {port}\nMode: {'incremental' if incremental else 'greenfield'}\n"
        f"Generate ONLY these paths: {paths}\n\n"
        f"Requirement / plan context:\n{final_spec[:12000]}\n"
        f"{plan_bits}\n"
        f"Current file contents (if any):\n" + "\n\n".join(existing_bits)
    )
    try:
        data = await chat_completion_json(
            system=_file_system_prompt(lang, port, incremental=incremental),
            user=user,
            max_retries=2,
        )
    except LlmError as e:
        raise CodegenError(str(e)) from e

    files = data.get("files")
    if not isinstance(files, list):
        raise CodegenError("JSON 缺少 files 数组")
    return _write_files(root, files, allow_paths=allow)


async def generate_project(
    lang: str,
    spec: str | None = None,
    *,
    use_docs: bool = True,
    repair_paths: list[str] | None = None,
) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise CodegenError(f"不支持的语言: {lang}")

    port = LANG_PORTS[lang]
    root = settings.auto_code_dir(lang)
    root.mkdir(parents=True, exist_ok=True)

    from backend.services import ir

    plan = ir.read_change_plan(lang) if use_docs else None
    incremental = bool(plan and str(plan.get("mode") or "") == "incremental" and _project_exists(lang, root))
    # 校验修复：只改报错文件（含同包 sibling），不重跑整份 plan
    repair_mode = bool(repair_paths) and _project_exists(lang, root)

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

    if repair_mode:
        # 修复轮：砍掉冗长 docs，优先靠 repair hints + 当前文件
        final_spec = (raw_spec or doc_spec or final_spec)[:4000]

    written: list[str] = []
    if repair_mode:
        targets = expand_repair_paths(root, list(repair_paths or []))
        if not targets:
            raise CodegenError("修复模式未解析到目标文件")
        logger.info("定点修复 lang=%s files=%d targets=%s", lang, len(targets), targets)
        for batch in _chunked(targets, 1):
            written.extend(
                await _generate_file_batch(
                    lang=lang,
                    port=port,
                    root=root,
                    paths=batch,
                    final_spec=final_spec,
                    plan=plan,
                    incremental=True,
                )
            )
    elif incremental:
        targets = _plan_target_files(plan)
        if not targets:
            targets = _fallback_existing_sources(lang, root)
        if not targets:
            raise CodegenError("增量模式未找到可修改的目标文件")
        logger.info("增量生成 lang=%s files=%d", lang, len(targets))
        for batch in _chunked(targets, 1):  # 每文件一次，降低 JSON 体积
            written.extend(
                await _generate_file_batch(
                    lang=lang,
                    port=port,
                    root=root,
                    paths=batch,
                    final_spec=final_spec,
                    plan=plan,
                    incremental=True,
                )
            )
    else:
        _clear_dir(root)
        batches = _greenfield_batches(lang)
        # 业务文件批：从 plan tasks 追加，否则让 LLM 在骨架后再补一轮业务
        plan_files = [p for p in _plan_target_files(plan) if p not in {x for b in batches for x in b}]
        if lang == "go":
            # Go 固定 go.mod + main.go，避免 plan 多文件与 main 符号冲突
            pass
        elif plan_files:
            batches.extend(_chunked(plan_files, 3))
        else:
            # Java 额外业务批
            batches.append([])  # 占位：下面特殊处理
        logger.info("从零生成 lang=%s batches=%d", lang, len(batches))
        for batch in batches:
            if not batch:
                # 自由业务批：请求 1～3 个业务文件
                user = (
                    f"Language: {lang}\nPort: {port}\nMode: greenfield\n"
                    "Generate 1 to 3 core domain files (entity/dto/repository/service/controller/tests) "
                    "needed by the requirements. Schema files array only.\n\n"
                    f"Requirements:\n{final_spec[:12000]}"
                )
                try:
                    data = await chat_completion_json(
                        system=_file_system_prompt(lang, port, incremental=False),
                        user=user,
                        max_retries=2,
                    )
                except LlmError as e:
                    raise CodegenError(str(e)) from e
                files = data.get("files")
                if not isinstance(files, list):
                    raise CodegenError("JSON 缺少 files 数组")
                # 限制最多 3 个
                written.extend(_write_files(root, files[:3], allow_paths=None))
                continue
            written.extend(
                await _generate_file_batch(
                    lang=lang,
                    port=port,
                    root=root,
                    paths=batch,
                    final_spec=final_spec,
                    plan=plan,
                    incremental=False,
                )
            )

    if raw_spec and not doc_spec:
        (root / "SPEC.md").write_text(raw_spec + "\n", encoding="utf-8", newline="\n")

    endpoints = _endpoints_from_plan(plan)
    mode = "repair" if repair_mode else ("incremental" if incremental else "greenfield")
    logger.info(
        "生成完成 lang=%s mode=%s files=%d port=%s",
        lang,
        mode,
        len(written),
        port,
    )
    return {
        "lang": lang,
        "port": port,
        "root": str(root),
        "files": written,
        "endpoints": endpoints,
        "used_docs": bool(doc_spec),
        "mode": mode,
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
    from backend.services.frontend_codegen import FRONTEND_PORT, ensure_shared_frontend

    fe_root = ensure_shared_frontend()
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
