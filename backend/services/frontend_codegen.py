from __future__ import annotations

import logging
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.core.config import LANG_PORTS, settings
from backend.services.analyze import AnalyzeError, load_docs_as_spec
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)

# 仅 java 产物配套 Vue；Agent 控制台占 5173/5174
FRONTEND_LANGS = frozenset({"java"})
FRONTEND_PORT = 5175
FRONTEND_DIR = "frontend"
RUN_BAT_NAME = "run_frontend.bat"


class FrontendCodegenError(RuntimeError):
    pass


def frontend_root(lang: str) -> Path:
    return settings.auto_code_dir(lang) / FRONTEND_DIR


def _system_prompt(*, backend_port: int, frontend_port: int) -> str:
    return (
        "You are a frontend code generation engine. Output a single JSON object only, no markdown.\n"
        "Schema:\n"
        "{\n"
        '  "files": [{"path": "relative/path", "content": "file content"}]\n'
        "}\n"
        "Rules:\n"
        "- Generate a complete runnable Vue 3 + Vite + TypeScript SPA (no login / no auth).\n"
        "- Must include: package.json, vite.config.ts, index.html, tsconfig.json, "
        "tsconfig.app.json, tsconfig.node.json, src/main.ts, src/App.vue, "
        "src/style.css, src/router/index.ts, src/api/client.ts, and page components "
        "that fully cover the business APIs in the requirement docs.\n"
        "- Use vue-router. Use native fetch (no axios). No UI component libraries "
        "(no Element Plus / Ant Design / Naive UI).\n"
        f"- Vite dev server port MUST be {frontend_port}.\n"
        f"- vite.config.ts MUST proxy '/api' and '/health' to "
        f"http://127.0.0.1:{backend_port} with changeOrigin true (no path rewrite).\n"
        "- Frontend calls MUST use relative URLs like '/api/...' and '/health' "
        "(go through Vite proxy), never hardcode backend host/port in page code.\n"
        "- Implement list/search, create, detail if API exists, and all mutation "
        "endpoints (PATCH/PUT/DELETE) with forms and error display using backend "
        "JSON fields code/message when present.\n"
        "- Chinese UI labels. Keep layout simple and usable.\n"
        "- package.json name: autocode-frontend; dependencies: vue, vue-router; "
        "devDependencies: vite, @vitejs/plugin-vue, typescript, vue-tsc, "
        "@vue/tsconfig, @types/node — use recent stable versions.\n"
        "- paths must be relative, use forward slashes, no .. or absolute paths.\n"
        "- content must be full file source, not placeholders.\n"
        "- Do NOT include node_modules or lockfiles.\n"
    )


def _safe_rel_path(raw: str) -> Path:
    rel = raw.replace("\\", "/").strip().lstrip("/")
    if rel.startswith("frontend/"):
        rel = rel[len("frontend/") :]
    if not rel or rel.startswith("..") or "/../" in f"/{rel}/":
        raise FrontendCodegenError(f"非法文件路径: {raw!r}")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        raise FrontendCodegenError(f"非法文件路径: {raw!r}")
    return path


def _clear_frontend(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


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
        raise FrontendCodegenError("LLM 未返回任何有效前端文件")
    return written


def _write_readme(root: Path, *, backend_port: int, frontend_port: int) -> str:
    body = (
        "# Auto-generated Vue Frontend\n\n"
        "无登录业务前端，通过 Vite 代理访问后端 API。\n\n"
        "## 启动\n\n"
        f"- 双击 `{RUN_BAT_NAME}`，或在本目录执行：\n\n"
        "```bash\n"
        "npm install\n"
        f"npm run dev -- --host 127.0.0.1 --port {frontend_port}\n"
        "```\n\n"
        f"- 前端: http://127.0.0.1:{frontend_port}\n"
        f"- 后端: http://127.0.0.1:{backend_port}\n"
        "- 请先启动对应语言后端，再启动本前端。\n"
    )
    path = root / "README.md"
    path.write_text(body, encoding="utf-8", newline="\n")
    return "README.md"


def _write_run_bat(root: Path, *, frontend_port: int) -> str:
    body = (
        "@echo off\n"
        "cd /d \"%~dp0\"\n"
        "echo [autocode] installing deps...\n"
        "call npm install\n"
        "if errorlevel 1 (\n"
        "  echo npm install failed\n"
        "  pause\n"
        "  exit /b 1\n"
        ")\n"
        f"echo [autocode] starting Vue frontend on http://127.0.0.1:{frontend_port}\n"
        f"call npm run dev -- --host 127.0.0.1 --port {frontend_port}\n"
        "pause\n"
    )
    path = root / RUN_BAT_NAME
    path.write_text(body, encoding="utf-8", newline="\r\n")
    return RUN_BAT_NAME


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except OSError:
        return False


def frontend_url(port: int | None = None) -> str:
    return f"http://127.0.0.1:{port or FRONTEND_PORT}"


def start_frontend_dev(lang: str, *, capture_log: bool = True) -> dict[str, Any]:
    """启动业务 Vue；默认把输出写入 auto_code/{lang}/logs/frontend.log 供页面展示。"""
    lang = lang.lower().strip()
    if lang not in FRONTEND_LANGS:
        raise FrontendCodegenError(f"当前仅支持启动 java 业务前端，收到: {lang}")

    root = frontend_root(lang)
    bat = root / RUN_BAT_NAME
    if not root.is_dir() or not any(root.iterdir()):
        raise FrontendCodegenError(f"尚未生成业务前端，请先生成代码: {root}")
    if not bat.is_file():
        _write_run_bat(root, frontend_port=FRONTEND_PORT)

    url = frontend_url(FRONTEND_PORT)
    already = _port_open("127.0.0.1", FRONTEND_PORT)
    log_file = settings.auto_code_dir(lang) / "logs" / "frontend.log"
    if already:
        return {
            "ok": True,
            "started": False,
            "already_running": True,
            "lang": lang,
            "port": FRONTEND_PORT,
            "url": url,
            "bat": str(bat),
            "log": str(log_file),
            "listening": True,
            "message": f"业务前端已在运行，可直接打开 {url}",
        }

    # Windows CreateProcess 找不到无扩展名的 npm，必须用 npm.cmd
    npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
    cmd = [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)]
    if capture_log:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8", newline="\n") as header:
            header.write(f"\n===== START {' '.join(cmd)} =====\n")
        handle = log_file.open("a", encoding="utf-8", newline="\n")
        kwargs: dict[str, Any] = {
            "cwd": str(root),
            "stdout": handle,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
        msg = f"已后台启动 Vue（pid={proc.pid}），日志见页面控制台；{url}"
        return {
            "ok": True,
            "started": True,
            "already_running": False,
            "lang": lang,
            "port": FRONTEND_PORT,
            "url": url,
            "bat": str(bat),
            "log": str(log_file),
            "pid": proc.pid,
            "listening": _port_open("127.0.0.1", FRONTEND_PORT),
            "message": msg,
        }

    if sys.platform.startswith("win"):
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "AutoCode Vue Frontend", str(bat.name)],
            cwd=str(root),
            shell=False,
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    return {
        "ok": True,
        "started": True,
        "already_running": False,
        "lang": lang,
        "port": FRONTEND_PORT,
        "url": url,
        "bat": str(bat),
        "log": str(log_file),
        "message": f"已启动 {RUN_BAT_NAME}，稍后打开 {url}",
    }


async def generate_frontend(
    lang: str,
    *,
    endpoints: list[dict[str, str]] | None = None,
    backend_port: int | None = None,
) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in FRONTEND_LANGS:
        return {
            "ok": False,
            "skipped": True,
            "lang": lang,
            "error": f"当前仅支持为 java 生成 Vue 前端，跳过: {lang}",
            "files": [],
        }

    api_port = backend_port if backend_port is not None else LANG_PORTS[lang]
    fe_port = FRONTEND_PORT
    root = frontend_root(lang)

    try:
        doc_spec = load_docs_as_spec(lang)
    except AnalyzeError as e:
        raise FrontendCodegenError(str(e)) from e

    plan_bits = ""
    try:
        from backend.services import ir

        plan = ir.read_change_plan(lang) or {}
        if plan:
            plan_bits = (
                "\n\n---\n\n# Change Plan APIs / data model\n\n"
                f"summary: {plan.get('summary')}\n"
                f"apis: {plan.get('apis')}\n"
                f"data_model: {plan.get('data_model')}\n"
            )
    except Exception:
        plan_bits = ""

    endpoints = endpoints or []
    ep_lines = "\n".join(
        f"- {e.get('method', 'GET')} {e.get('path', '')}: {e.get('description', '')}"
        for e in endpoints
        if isinstance(e, dict) and e.get("path")
    )
    user = (
        f"Backend language: {lang}\n"
        f"Backend port: {api_port}\n"
        f"Frontend port: {fe_port}\n\n"
        f"Known endpoints:\n{ep_lines or '(see docs)'}\n\n"
        f"Requirement documents:\n{doc_spec}"
        f"{plan_bits}"
    )

    try:
        raw = await chat_completion(system=_system_prompt(backend_port=api_port, frontend_port=fe_port), user=user)
    except LlmError as e:
        raise FrontendCodegenError(str(e)) from e

    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise FrontendCodegenError(str(e)) from e

    files = data.get("files")
    if not isinstance(files, list):
        raise FrontendCodegenError("JSON 缺少 files 数组")

    _clear_frontend(root)
    written = _write_files(root, files)
    written.append(_write_readme(root, backend_port=api_port, frontend_port=fe_port))
    written.append(_write_run_bat(root, frontend_port=fe_port))

    logger.info("前端生成完成 lang=%s files=%d port=%s", lang, len(written), fe_port)
    return {
        "ok": True,
        "skipped": False,
        "lang": lang,
        "port": fe_port,
        "backend_port": api_port,
        "root": str(root),
        "files": written,
        "error": None,
    }


__all__ = [
    "FRONTEND_DIR",
    "FRONTEND_LANGS",
    "FRONTEND_PORT",
    "RUN_BAT_NAME",
    "FrontendCodegenError",
    "frontend_root",
    "frontend_url",
    "generate_frontend",
    "start_frontend_dev",
]
