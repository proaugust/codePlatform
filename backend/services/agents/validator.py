from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services import ir

logger = logging.getLogger(__name__)

# go build / javac 风格：path:line: 或 path:line:col:
_ERR_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[\w./\\-]+\.(?:go|java)):\d+(?::\d+)?:",
)


class ValidatorError(RuntimeError):
    pass


def parse_error_paths(text: str) -> list[str]:
    """从编译 stderr/stdout 提取相对源文件路径（去重保序）。"""
    found: list[str] = []
    seen: set[str] = set()
    for m in _ERR_PATH_RE.finditer(text or ""):
        raw = m.group("path").replace("\\", "/")
        # 丢掉绝对路径前缀，尽量落到工程相对路径
        if re.match(r"^[A-Za-z]:/", raw):
            # Windows 绝对路径：取最后带 src/ 或 internal/ 的后缀，否则取 basename 所在相对段
            parts = Path(raw).parts
            for i, part in enumerate(parts):
                if part in {"internal", "src", "cmd", "pkg"}:
                    raw = "/".join(parts[i:])
                    break
            else:
                raw = Path(raw).name
        raw = raw.lstrip("./")
        if raw and raw not in seen:
            seen.add(raw)
            found.append(raw)
    return found


def _run_cmd(cmd: list[str], cwd: Path, timeout: float = 120.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": cmd,
            "ok": False,
            "returncode": -1,
            "stdout": (e.stdout or "")[:4000] if isinstance(e.stdout, str) else "",
            "stderr": f"timeout after {timeout}s",
        }
    except OSError as e:
        return {
            "cmd": cmd,
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }
    out = (proc.stdout or "")[-4000:]
    err = (proc.stderr or "")[-4000:]
    return {
        "cmd": cmd,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": out,
        "stderr": err,
    }


def _which(name: str) -> str | None:
    return shutil.which(name)


async def run_validator(lang: str, *, repair_count: int = 0) -> dict[str, Any]:
    root = settings.auto_code_dir(lang)
    commands: list[dict[str, Any]] = []
    skipped: list[str] = []

    if lang == "java":
        mvn = _which("mvn") or _which("mvn.cmd")
        if not mvn:
            skipped.append("未找到 mvn，跳过编译检查")
        elif not (root / "pom.xml").is_file():
            return _finish(
                lang,
                ok=False,
                skipped=skipped,
                commands=commands,
                repair_count=repair_count,
                repair_hints="缺少 pom.xml，请生成完整 Maven 工程。",
            )
        else:
            commands.append(_run_cmd([mvn, "-q", "-DskipTests", "compile"], root))
    else:
        go = _which("go") or _which("go.exe")
        if not go:
            skipped.append("未找到 go，跳过编译检查")
        elif not (root / "go.mod").is_file():
            return _finish(
                lang,
                ok=False,
                skipped=skipped,
                commands=commands,
                repair_count=repair_count,
                repair_hints="缺少 go.mod，请生成完整 Go 工程。",
            )
        else:
            commands.append(_run_cmd([go, "build", "./..."], root))

    if not commands and skipped:
        return _finish(
            lang,
            ok=True,
            skipped=skipped,
            commands=commands,
            repair_count=repair_count,
            repair_hints="",
            note="工具链缺失，校验跳过视为通过（demo）",
        )

    failed = [c for c in commands if not c.get("ok")]
    if failed:
        hints = []
        blob_parts: list[str] = []
        for c in failed:
            stderr = c.get("stderr") or ""
            stdout = c.get("stdout") or ""
            blob_parts.extend([stderr, stdout])
            hints.append(
                f"command: {' '.join(c.get('cmd') or [])}\n"
                f"returncode: {c.get('returncode')}\n"
                f"stderr:\n{stderr}\n"
                f"stdout:\n{stdout}\n"
            )
        repair_files = parse_error_paths("\n".join(blob_parts))
        return _finish(
            lang,
            ok=False,
            skipped=skipped,
            commands=commands,
            repair_count=repair_count,
            repair_hints=(
                "\n".join(hints)
                + "\n请只修复报错涉及的文件；同包可补充缺失 helper（如 undefined 的函数），"
                "不要重写无关文件。输出 JSON files。\n"
                + (f"报错文件: {repair_files}\n" if repair_files else "")
            ),
            repair_files=repair_files,
        )

    return _finish(
        lang,
        ok=True,
        skipped=skipped,
        commands=commands,
        repair_count=repair_count,
        repair_hints="",
        repair_files=[],
    )


def _finish(
    lang: str,
    *,
    ok: bool,
    skipped: list[str],
    commands: list[dict[str, Any]],
    repair_count: int,
    repair_hints: str,
    note: str = "",
    repair_files: list[str] | None = None,
) -> dict[str, Any]:
    # 不把完整 cmd list 原样塞进 JSON 时转换一下
    cmds_out = []
    for c in commands:
        cmds_out.append(
            {
                "cmd": " ".join(c.get("cmd") or []),
                "ok": c.get("ok"),
                "returncode": c.get("returncode"),
                "stdout": c.get("stdout") or "",
                "stderr": c.get("stderr") or "",
            }
        )
    payload = {
        "lang": lang,
        "ok": ok,
        "skipped": skipped,
        "commands": cmds_out,
        "repair_count": repair_count,
        "repair_hints": repair_hints,
        "repair_files": list(repair_files or []),
        "note": note,
    }
    path = ir.write_validation(lang, payload)
    logger.info(
        "Validator lang=%s ok=%s repairs=%s files=%s path=%s",
        lang,
        ok,
        repair_count,
        payload["repair_files"],
        path,
    )
    return payload
