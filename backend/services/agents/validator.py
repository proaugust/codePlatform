from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services import ir

logger = logging.getLogger(__name__)


class ValidatorError(RuntimeError):
    pass


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
        for c in failed:
            hints.append(
                f"command: {' '.join(c.get('cmd') or [])}\n"
                f"returncode: {c.get('returncode')}\n"
                f"stderr:\n{c.get('stderr') or ''}\n"
                f"stdout:\n{c.get('stdout') or ''}\n"
            )
        return _finish(
            lang,
            ok=False,
            skipped=skipped,
            commands=commands,
            repair_count=repair_count,
            repair_hints="\n".join(hints) + "\n请修复编译错误并重新输出完整可编译工程（JSON files）。",
        )

    return _finish(
        lang,
        ok=True,
        skipped=skipped,
        commands=commands,
        repair_count=repair_count,
        repair_hints="",
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
        "note": note,
    }
    path = ir.write_validation(lang, payload)
    logger.info("Validator lang=%s ok=%s repairs=%s path=%s", lang, ok, repair_count, path)
    return payload
