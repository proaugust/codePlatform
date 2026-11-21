from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, IO

from backend.core.config import LANG_PORTS, settings
from backend.services.analyze import AnalyzeError, load_docs_as_spec
from backend.services.llm import LlmError, chat_completion_json

logger = logging.getLogger(__name__)

# java/go 产物均可配套 Vue；Agent 控制台占 5173/5174，业务前端共用 5175
FRONTEND_LANGS = frozenset({"java", "go"})
FRONTEND_PORT = 5175
FRONTEND_DIR = "frontend"
RUN_BAT_NAME = "run_frontend.bat"


class FrontendCodegenError(RuntimeError):
    pass


def frontend_root(lang: str) -> Path:
    return settings.auto_code_dir(lang) / FRONTEND_DIR


def _system_prompt(*, backend_port: int, frontend_port: int, incremental: bool) -> str:
    if incremental:
        scope = (
            "Incremental edit of an existing Vue SPA. Output ONLY the requested paths "
            "(typically src/api/client.ts, list/detail views, router). Preserve unrelated pages. "
            "Must wire DELETE/PATCH/PUT mutations when those APIs exist (select target then call API)."
        )
    else:
        scope = (
            "Generate a complete runnable Vue 3 + Vite + TypeScript SPA (no login / no auth). "
            "Must include: package.json, vite.config.ts, index.html, tsconfig.json, "
            "tsconfig.app.json, tsconfig.node.json, src/main.ts, src/App.vue, "
            "src/style.css, src/router/index.ts, src/api/client.ts, and page components "
            "that fully cover the business APIs in the requirement docs."
        )
    return (
        "You are a frontend code generation engine. Output a single JSON object only, no markdown.\n"
        "Schema:\n"
        "{\n"
        '  "files": [{"path": "relative/path", "content": "file content"}]\n'
        "}\n"
        "Rules:\n"
        f"- {scope}\n"
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
        "- Return at most 4 files per response.\n"
    )


def _frontend_incremental_targets(root: Path, plan: dict[str, Any] | None) -> list[str]:
    """已有 frontend 时优先改 API 客户端与列表/详情页。"""
    from_plan: list[str] = []
    seen: set[str] = set()
    for task in (plan or {}).get("tasks") or []:
        if not isinstance(task, dict):
            continue
        for f in task.get("files") or []:
            s = str(f).replace("\\", "/").strip()
            if s.startswith("frontend/"):
                s = s[len("frontend/") :]
            if not s.startswith("src/") or s in seen:
                continue
            if ".." in s:
                continue
            seen.add(s)
            from_plan.append(s)
    defaults = [
        "src/api/client.ts",
        "src/views/BookListView.vue",
        "src/views/BookDetailView.vue",
        "src/router/index.ts",
        "src/types.ts",
    ]
    # 只保留磁盘已有或 plan 点名的；新建缺失的 client/list
    out: list[str] = []
    for p in from_plan + defaults:
        if p in out:
            continue
        if (root / p).is_file() or p in ("src/api/client.ts", "src/views/BookListView.vue"):
            out.append(p)
        if len(out) >= 4:
            break
    return out or ["src/api/client.ts", "src/views/BookListView.vue"]


def _read_fe_snippet(root: Path, rel: str, *, max_chars: int = 5000) -> str:
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
    """清空前端目录；先停占端口进程，避免 Windows 锁住 node_modules/esbuild。"""
    from backend.services.runtime import kill_port

    kill_port(FRONTEND_PORT)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return

    last_err: OSError | None = None
    for i in range(5):
        try:
            shutil.rmtree(root)
            last_err = None
            break
        except OSError as e:
            last_err = e
            # 再杀一次端口，给句柄释放时间
            kill_port(FRONTEND_PORT)
            time.sleep(0.5 * (i + 1))
            # 尝试先挪走被锁的 node_modules
            nm = root / "node_modules"
            if nm.is_dir():
                trash = root.parent / f".frontend_nm_trash_{int(time.time())}_{i}"
                try:
                    nm.rename(trash)
                except OSError:
                    pass
    if last_err is not None and root.exists():
        raise FrontendCodegenError(
            f"无法清空前端目录（请先在「运行」页停止前端后再执行生成）: {last_err}"
        ) from last_err
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


def _vite_bin(root: Path) -> Path | None:
    if sys.platform.startswith("win"):
        cmd = root / "node_modules" / ".bin" / "vite.cmd"
    else:
        cmd = root / "node_modules" / ".bin" / "vite"
    return cmd if cmd.is_file() else None


def _append_frontend_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _ensure_frontend_deps(root: Path, log_file: Path) -> None:
    """node_modules/.bin/vite 缺失时自动 npm install（常见于残缺安装）。"""
    if _vite_bin(root) is not None:
        return
    npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
    _append_frontend_log(log_file, f"\n===== deps: {npm} install（缺少 vite 可执行文件） =====\n")
    handle = log_file.open("a", encoding="utf-8", newline="\n")
    try:
        kwargs: dict[str, Any] = {
            "cwd": str(root),
            "stdout": handle,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        proc = subprocess.run([npm, "install"], **kwargs, timeout=300)
    except subprocess.TimeoutExpired as e:
        raise FrontendCodegenError("npm install 超时（300s），请到 frontend 目录手动安装依赖") from e
    finally:
        handle.close()
    if proc.returncode != 0:
        raise FrontendCodegenError(
            f"npm install 失败（exit={proc.returncode}），请查看 frontend 日志"
        )
    if _vite_bin(root) is None:
        raise FrontendCodegenError(
            "npm install 后仍缺少 node_modules/.bin/vite，请到 frontend 目录手动 npm install"
        )
    _append_frontend_log(log_file, "===== deps: npm install ok =====\n")


def _tail_log_text(path: Path, *, max_chars: int = 2500) -> str:
    if not path.is_file():
        return ""
    raw = path.read_bytes()
    chunk = raw[-max_chars:] if len(raw) > max_chars else raw
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return chunk.decode(enc)
        except UnicodeDecodeError:
            continue
    return chunk.decode("utf-8", errors="replace")


def _wait_frontend_ready(
    proc: subprocess.Popen[Any],
    *,
    port: int,
    log_file: Path,
    timeout_s: float = 25.0,
) -> tuple[bool, str]:
    """等待端口就绪或进程退出；失败时带上日志尾部。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _port_open("127.0.0.1", port):
            return True, f"业务前端已监听 http://127.0.0.1:{port}"
        code = proc.poll()
        if code is not None:
            tail = _tail_log_text(log_file).strip()
            detail = f"\n---- log ----\n{tail}" if tail else ""
            return False, f"Vue 前端进程已退出（exit={code}）{detail}"
        time.sleep(0.35)
    if _port_open("127.0.0.1", port):
        return True, f"业务前端已监听 http://127.0.0.1:{port}"
    code = proc.poll()
    if code is not None:
        tail = _tail_log_text(log_file).strip()
        detail = f"\n---- log ----\n{tail}" if tail else ""
        return False, f"Vue 前端进程已退出（exit={code}）{detail}"
    return (
        False,
        f"启动超时（{int(timeout_s)}s）仍未监听 :{port}，请查看 frontend 日志",
    )


def start_frontend_dev(lang: str, *, capture_log: bool = True) -> dict[str, Any]:
    """启动业务 Vue；默认把输出写入 auto_code/{lang}/logs/frontend.log 供页面展示。"""
    lang = lang.lower().strip()
    if lang not in FRONTEND_LANGS:
        raise FrontendCodegenError(f"不支持启动业务前端的语言: {lang}（可选: java, go）")

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

    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        _ensure_frontend_deps(root, log_file)
    except FrontendCodegenError:
        raise

    # Windows CreateProcess 找不到无扩展名的 npm，必须用 npm.cmd
    npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
    cmd = [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)]
    if capture_log:
        _append_frontend_log(log_file, f"\n===== START {' '.join(cmd)} =====\n")
        # 二进制追加：兼容 npm/cmd 的系统编码输出，避免中文错误被 utf-8 读丢
        handle: IO[bytes] = log_file.open("ab")
        env = os.environ.copy()
        env.setdefault("FORCE_COLOR", "0")
        kwargs: dict[str, Any] = {
            "cwd": str(root),
            "stdout": handle,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "env": env,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
        ok, msg = _wait_frontend_ready(proc, port=FRONTEND_PORT, log_file=log_file)
        listening = _port_open("127.0.0.1", FRONTEND_PORT)
        if not ok:
            _append_frontend_log(log_file, f"===== START FAILED =====\n{msg}\n")
        return {
            "ok": ok,
            "started": True,
            "already_running": False,
            "lang": lang,
            "port": FRONTEND_PORT,
            "url": url,
            "bat": str(bat),
            "log": str(log_file),
            "pid": proc.pid,
            "listening": listening,
            "message": msg if ok else f"前端启动失败：{msg}",
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
            "error": f"不支持为 {lang} 生成 Vue 前端，跳过",
            "files": [],
        }

    api_port = backend_port if backend_port is not None else LANG_PORTS[lang]
    fe_port = FRONTEND_PORT
    root = frontend_root(lang)

    try:
        doc_spec = load_docs_as_spec(lang)
    except AnalyzeError as e:
        raise FrontendCodegenError(str(e)) from e

    plan: dict[str, Any] = {}
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
                f"tasks: {plan.get('tasks')}\n"
            )
    except Exception:
        plan_bits = ""

    endpoints = endpoints or []
    ep_lines = "\n".join(
        f"- {e.get('method', 'GET')} {e.get('path', '')}: {e.get('description', '')}"
        for e in endpoints
        if isinstance(e, dict) and e.get("path")
    )
    incremental = (root / "package.json").is_file()
    system = _system_prompt(backend_port=api_port, frontend_port=fe_port, incremental=incremental)

    written: list[str] = []
    if incremental:
        targets = _frontend_incremental_targets(root, plan)
        snippets = "\n\n".join(f"### {p}\n```\n{_read_fe_snippet(root, p)}\n```" for p in targets)
        user = (
            f"Backend language: {lang}\n"
            f"Backend port: {api_port}\n"
            f"Frontend port: {fe_port}\n"
            f"Mode: incremental\n"
            f"Generate ONLY these paths: {targets}\n\n"
            f"Known endpoints:\n{ep_lines or '(see docs)'}\n\n"
            f"Requirement documents:\n{doc_spec[:8000]}"
            f"{plan_bits}\n\n"
            f"Current files:\n{snippets}"
        )
        try:
            data = await chat_completion_json(system=system, user=user, max_retries=2)
        except LlmError as e:
            raise FrontendCodegenError(str(e)) from e
        files = data.get("files")
        if not isinstance(files, list):
            raise FrontendCodegenError("JSON 缺少 files 数组")
        # overlay，不清空 frontend / node_modules
        written = _write_files(root, files)
        written.append(_write_readme(root, backend_port=api_port, frontend_port=fe_port))
        written.append(_write_run_bat(root, frontend_port=fe_port))
    else:
        # 从零：两批（工程配置 + src）
        scaffold_user = (
            f"Backend language: {lang}\nBackend port: {api_port}\nFrontend port: {fe_port}\n"
            "Mode: greenfield scaffold batch.\n"
            "Generate ONLY: package.json, vite.config.ts, index.html, tsconfig.json, "
            "tsconfig.app.json, tsconfig.node.json (max 4 files this turn if needed split).\n\n"
            f"Known endpoints:\n{ep_lines or '(see docs)'}\n\n"
            f"Requirement documents:\n{doc_spec[:6000]}{plan_bits}"
        )
        src_user = (
            f"Backend language: {lang}\nBackend port: {api_port}\nFrontend port: {fe_port}\n"
            "Mode: greenfield src batch.\n"
            "Generate src/main.ts, src/App.vue, src/style.css, src/router/index.ts, "
            "src/api/client.ts, and page views covering list/create/detail and DELETE/PATCH.\n"
            "Max 4 files per response — prioritize client + list + router + types.\n\n"
            f"Known endpoints:\n{ep_lines or '(see docs)'}\n\n"
            f"Requirement documents:\n{doc_spec[:8000]}{plan_bits}"
        )
        _clear_frontend(root)
        for user in (scaffold_user, src_user):
            try:
                data = await chat_completion_json(system=system, user=user, max_retries=2)
            except LlmError as e:
                raise FrontendCodegenError(str(e)) from e
            files = data.get("files")
            if not isinstance(files, list):
                raise FrontendCodegenError("JSON 缺少 files 数组")
            written.extend(_write_files(root, files[:4]))
        written.append(_write_readme(root, backend_port=api_port, frontend_port=fe_port))
        written.append(_write_run_bat(root, frontend_port=fe_port))

    logger.info(
        "前端生成完成 lang=%s mode=%s files=%d port=%s",
        lang,
        "incremental" if incremental else "greenfield",
        len(written),
        fe_port,
    )
    return {
        "ok": True,
        "skipped": False,
        "lang": lang,
        "port": fe_port,
        "backend_port": api_port,
        "root": str(root),
        "files": written,
        "error": None,
        "mode": "incremental" if incremental else "greenfield",
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
