from __future__ import annotations

import logging
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO

from backend.core.config import LANG_PORTS, settings
from backend.services.frontend_codegen import (
    FRONTEND_PORT,
    FrontendCodegenError,
    ensure_shared_frontend,
    start_frontend_dev,
)

logger = logging.getLogger(__name__)

RUN_BACKEND_BAT = "run_backend.bat"
LOG_DIR_NAME = "logs"
BACKEND_LOG = "backend.log"
FRONTEND_LOG = "frontend.log"


class ProjectRuntimeError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except OSError:
        return False


def _pids_on_port(port: int) -> list[int]:
    if not sys.platform.startswith("win"):
        return []
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            errors="ignore",
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    pids: set[int] = set()
    needle = f":{port} "
    for line in out.splitlines():
        if needle not in line or "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return sorted(pids)


def kill_port(port: int) -> list[int]:
    """结束占用端口的进程（Windows）；返回被杀 PID。"""
    killed: list[int] = []
    for pid in _pids_on_port(port):
        if pid <= 0:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                check=False,
                capture_output=True,
                text=True,
            )
            killed.append(pid)
        except OSError as e:
            logger.warning("taskkill pid=%s failed: %s", pid, e)
    if killed:
        time.sleep(0.8)
    return killed


def logs_dir(lang: str) -> Path:
    path = settings.auto_code_dir(lang) / LOG_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path(lang: str, kind: str) -> Path:
    name = FRONTEND_LOG if kind == "frontend" else BACKEND_LOG
    return logs_dir(lang) / name


def _append_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _open_log_handle(path: Path) -> IO[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8", newline="\n")


def _java_sources_newer_than(root: Path, artifact: Path) -> bool:
    """源码比产物新时，避免继续跑旧 jar（如异常处理已改但未重新打包）。"""
    try:
        art_mtime = artifact.stat().st_mtime
    except OSError:
        return True
    src = root / "src"
    if not src.is_dir():
        return False
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime > art_mtime:
                return True
        except OSError:
            continue
    return False


def _java_cmd(root: Path) -> list[str]:
    jar_candidates = sorted((root / "target").glob("*.jar")) if (root / "target").is_dir() else []
    jar_candidates = [p for p in jar_candidates if not p.name.endswith(".original")]
    if jar_candidates:
        jar = jar_candidates[-1]
        if not _java_sources_newer_than(root, jar):
            return ["java", "-jar", str(jar)]
    return ["mvn", "-DskipTests", "spring-boot:run"]


def _write_java_bat(root: Path, port: int) -> Path:
    """保留 bat 便于手动双击；页面内启动不再依赖它。"""
    bat = root / RUN_BACKEND_BAT
    cmd = _java_cmd(root)
    lines = [
        "@echo off",
        "setlocal",
        f"cd /d \"{root}\"",
        f"echo [autocode] starting Java backend on http://127.0.0.1:{port}",
        " ".join(f'"{c}"' if " " in c else c for c in cmd),
        "echo [autocode] process exited with code %ERRORLEVEL%",
        "pause",
        "endlocal",
    ]
    bat.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="\r\n")
    return bat


def _write_go_bat(root: Path, port: int) -> Path:
    bat = root / RUN_BACKEND_BAT
    lines = [
        "@echo off",
        f"cd /d \"{root}\"",
        f"echo [autocode] starting Go backend on http://127.0.0.1:{port}",
        "go run .",
        "echo [autocode] process exited with code %ERRORLEVEL%",
        "pause",
    ]
    bat.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="\r\n")
    return bat


def _go_root(lang_root: Path) -> Path | None:
    if (lang_root / "main.go").is_file() or (lang_root / "go.mod").is_file():
        return lang_root
    code = lang_root / "code"
    if (code / "main.go").is_file() or (code / "go.mod").is_file():
        return code
    for p in lang_root.rglob("main.go"):
        if "docs" in p.parts:
            continue
        return p.parent
    return None


def _popen_logged(cmd: list[str], *, cwd: Path, log: Path) -> subprocess.Popen[Any]:
    _append_log(log, f"\n===== {_now()} START {' '.join(cmd)} =====")
    handle = _open_log_handle(log)
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdout": handle,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform.startswith("win"):
        # 不弹新控制台：日志进文件，页面轮询展示
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    _append_log(log, f"[{_now()}] pid={proc.pid}")
    return proc


def _wait_listening(port: int, *, timeout_sec: float = 25.0) -> bool:
    """Spring Boot 常需十余秒才监听；过短会导致页面仍显示「启动」按钮。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _port_open("127.0.0.1", port):
            return True
        time.sleep(0.35)
    return _port_open("127.0.0.1", port)


def _http_json(method: str, url: str, *, body: dict[str, Any] | None = None, timeout: float = 5.0) -> tuple[int, Any]:
    import json
    import urllib.error
    import urllib.request

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            payload: Any = raw
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    pass
            return int(resp.status), payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        payload: Any = raw
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                pass
        return int(e.code), payload
    except OSError as e:
        return 0, str(e)


def smoke_after_generate(
    lang: str,
    *,
    plan: dict[str, Any] | None = None,
    endpoints: list[Any] | None = None,
) -> dict[str, Any]:
    """生成后冒烟：健康检查；若计划含图书 DELETE 则 create→delete 验证（后端需已在听）。"""
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        return {"ok": False, "skipped": True, "message": f"不支持的 lang={lang}"}

    port = LANG_PORTS[lang]
    base = f"http://127.0.0.1:{port}"
    if not _port_open("127.0.0.1", port):
        return {
            "ok": False,
            "skipped": True,
            "listening": False,
            "message": f"后端未监听 {port}，跳过冒烟（请先启动后再测删除等接口）",
        }

    status, health = _http_json("GET", f"{base}/health")
    if status != 200:
        return {
            "ok": False,
            "skipped": False,
            "listening": True,
            "message": f"GET /health 失败 HTTP {status}: {health}",
        }

    apis = list((plan or {}).get("apis") or [])
    for ep in endpoints or []:
        if isinstance(ep, dict):
            apis.append(ep)

    want_book_delete = False
    for ep in apis:
        if not isinstance(ep, dict):
            continue
        method = str(ep.get("method") or "").upper()
        path = str(ep.get("path") or "")
        if method == "DELETE" and "/api/books" in path:
            want_book_delete = True
            break

    if not want_book_delete:
        return {
            "ok": True,
            "skipped": False,
            "listening": True,
            "message": "GET /health 通过；计划未含图书 DELETE，未跑删除冒烟",
        }

    isbn = f"smoke{int(time.time()) % 10_000_000:07d}"
    st, created = _http_json(
        "POST",
        f"{base}/api/books",
        body={"title": "smoke-book", "author": "smoke", "isbn": isbn, "stock": 1},
    )
    if st not in {200, 201} or not isinstance(created, dict) or created.get("id") is None:
        return {
            "ok": False,
            "skipped": False,
            "listening": True,
            "message": f"图书 DELETE 冒烟：创建失败 HTTP {st}: {created}",
        }

    book_id = created.get("id")
    st2, deleted = _http_json("DELETE", f"{base}/api/books/{book_id}")
    if st2 not in {200, 204}:
        return {
            "ok": False,
            "skipped": False,
            "listening": True,
            "message": f"图书 DELETE 冒烟：删除失败 HTTP {st2}: {deleted}",
        }

    st3, _ = _http_json("GET", f"{base}/api/books/{book_id}")
    if st3 not in {404, 400}:
        return {
            "ok": False,
            "skipped": False,
            "listening": True,
            "message": f"图书 DELETE 冒烟：删除后仍可访问 HTTP {st3}",
        }

    return {
        "ok": True,
        "skipped": False,
        "listening": True,
        "message": f"GET /health 通过；图书 DELETE 冒烟通过（id={book_id}）",
    }


def _normalize_log_kind(kind: str) -> str:
    kind = kind.lower().strip()
    if kind not in {"backend", "frontend"}:
        raise ProjectRuntimeError("kind 仅支持 backend | frontend")
    return kind


def _decode_log_bytes(data: bytes) -> str:
    """运行日志可能混有 UTF-8（Vite）与系统编码（Windows cmd 中文错误）。"""
    if not data:
        return ""
    scored: list[tuple[int, int, str]] = []
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            text = data.decode(enc)
            bad = 0
        except UnicodeDecodeError:
            text = data.decode(enc, errors="replace")
            bad = text.count("\ufffd")
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        scored.append((bad, -cjk, text))
    scored.sort()
    return scored[0][2]


def read_runtime_log(lang: str, kind: str, *, max_chars: int = 20000) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")
    kind = _normalize_log_kind(kind)

    path = log_path(lang, kind)
    port = FRONTEND_PORT if kind == "frontend" else LANG_PORTS[lang]
    text = ""
    if path.is_file():
        raw = path.read_bytes()
        decoded = _decode_log_bytes(raw)
        text = decoded[-max_chars:] if len(decoded) > max_chars else decoded
    return {
        "lang": lang,
        "kind": kind,
        "path": str(path),
        "exists": path.is_file(),
        "listening": _port_open("127.0.0.1", port),
        "port": port,
        "url": f"http://127.0.0.1:{port}",
        "text": text,
        "updated_at": _now(),
    }


def clear_runtime_log(lang: str, kind: str) -> dict[str, Any]:
    """清空对应 runtime 日志文件（写入一条 cleared 标记）。"""
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")
    kind = _normalize_log_kind(kind)
    path = log_path(lang, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f"[{_now()}] cleared\n"
    try:
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(marker)
    except OSError as e:
        raise ProjectRuntimeError(f"清空日志失败: {e}") from e
    return read_runtime_log(lang, kind)


def restart_project(lang: str, *, with_frontend: bool = True) -> dict[str, Any]:
    """杀掉占用端口后启动生成产物；stdout/stderr 写入 logs/*.log 供页面展示。"""
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")

    root = settings.auto_code_dir(lang)
    port = LANG_PORTS[lang]
    blog = log_path(lang, "backend")
    backend: dict[str, Any] = {
        "ok": False,
        "started": False,
        "killed": [],
        "port": port,
        "root": str(root),
        "log": str(blog),
        "message": "",
    }
    frontend: dict[str, Any] | None = None

    if lang == "java":
        if not (root / "pom.xml").is_file():
            raise ProjectRuntimeError(f"尚未生成 Java 工程: {root}")
        killed = kill_port(port)
        bat = _write_java_bat(root, port)
        cmd = _java_cmd(root)
        proc = _popen_logged(cmd, cwd=root, log=blog)
        listening = _wait_listening(port)
        url = f"http://127.0.0.1:{port}"
        backend.update(
            {
                "ok": True,
                "started": True,
                "listening": listening,
                "pid": proc.pid,
                "killed": killed,
                "bat": str(bat),
                "cmd": cmd,
                "url": url,
                "message": (
                    f"Java 后端已监听 {url}"
                    if listening
                    else f"已后台启动 Java（pid={proc.pid}），日志见页面控制台；端口 {port} 启动中…"
                ),
            }
        )
        if with_frontend:
            fe = ensure_shared_frontend()
            if fe.is_dir() and any(fe.iterdir()):
                fe_killed = kill_port(FRONTEND_PORT)
                try:
                    frontend = start_frontend_dev(lang, capture_log=True)
                    frontend["killed"] = fe_killed
                except FrontendCodegenError as e:
                    frontend = {
                        "ok": False,
                        "started": False,
                        "killed": fe_killed,
                        "error": str(e),
                        "message": str(e),
                    }
    elif lang == "go":
        go_root = _go_root(root)
        if not go_root:
            raise ProjectRuntimeError(f"尚未生成 Go 工程（缺少 main.go）: {root}")
        killed = kill_port(port)
        bat = _write_go_bat(go_root, port)
        proc = _popen_logged(["go", "run", "."], cwd=go_root, log=blog)
        listening = _wait_listening(port)
        url = f"http://127.0.0.1:{port}"
        backend.update(
            {
                "ok": True,
                "started": True,
                "listening": listening,
                "pid": proc.pid,
                "killed": killed,
                "bat": str(bat),
                "root": str(go_root),
                "url": url,
                "message": (
                    f"Go 后端已监听 {url}"
                    if listening
                    else f"已后台启动 Go（pid={proc.pid}），日志见页面控制台；端口 {port} 启动中…"
                ),
            }
        )
        if with_frontend:
            fe = ensure_shared_frontend()
            if fe.is_dir() and any(fe.iterdir()):
                fe_killed = kill_port(FRONTEND_PORT)
                try:
                    frontend = start_frontend_dev(lang, capture_log=True)
                    frontend["killed"] = fe_killed
                except FrontendCodegenError as e:
                    frontend = {
                        "ok": False,
                        "started": False,
                        "killed": fe_killed,
                        "error": str(e),
                        "message": str(e),
                    }
    else:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")

    return {
        "ok": bool(backend.get("ok")),
        "lang": lang,
        "backend": backend,
        "frontend": frontend,
        "message": backend.get("message") or "",
    }


def stop_backend(lang: str) -> dict[str, Any]:
    """停止占用后端端口的进程。"""
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")

    port = LANG_PORTS[lang]
    was_listening = _port_open("127.0.0.1", port)
    killed = kill_port(port)
    still = _port_open("127.0.0.1", port)
    blog = log_path(lang, "backend")
    if killed:
        _append_log(blog, f"[{_now()}] STOP backend port={port} killed={killed}")
    msg = (
        f"已停止 {lang} 后端（端口 {port}，killed={killed}）"
        if killed
        else (
            f"{lang} 后端端口 {port} 原本未监听"
            if not was_listening
            else f"未能停止 {lang} 后端（端口 {port} 仍在监听）"
        )
    )
    return {
        "ok": not still,
        "lang": lang,
        "kind": "backend",
        "port": port,
        "killed": killed,
        "listening": still,
        "url": f"http://127.0.0.1:{port}",
        "message": msg,
    }


def stop_frontend(lang: str) -> dict[str, Any]:
    """停止占用前端端口的进程。"""
    lang = lang.lower().strip()
    if lang not in LANG_PORTS:
        raise ProjectRuntimeError(f"不支持的 target: {lang}")

    port = FRONTEND_PORT
    was_listening = _port_open("127.0.0.1", port)
    killed = kill_port(port)
    still = _port_open("127.0.0.1", port)
    flog = log_path(lang, "frontend")
    if killed:
        _append_log(flog, f"[{_now()}] STOP frontend port={port} killed={killed}")
    msg = (
        f"已停止 Vue 前端（端口 {port}，killed={killed}）"
        if killed
        else (
            f"Vue 前端端口 {port} 原本未监听"
            if not was_listening
            else f"未能停止 Vue 前端（端口 {port} 仍在监听）"
        )
    )
    return {
        "ok": not still,
        "lang": lang,
        "kind": "frontend",
        "port": port,
        "killed": killed,
        "listening": still,
        "url": f"http://127.0.0.1:{port}",
        "message": msg,
    }
