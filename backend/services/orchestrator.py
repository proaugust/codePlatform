from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.core.config import settings
from backend.services import ir
from backend.services.agents.coder import run_coder
from backend.services.agents.planner import PlannerError, run_planner
from backend.services.agents.repo_intel import run_repo_intel
from backend.services.agents.requirements import RequirementsError, run_requirements
from backend.services.agents.validator import run_validator
from backend.services.analyze import docs_dir, read_docs
from backend.services.codegen import CodegenError, SUPPORTED_LANGS

logger = logging.getLogger(__name__)


class OrchestratorError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_run(lang: str, state: str, **extra: Any) -> dict[str, Any]:
    prev = ir.read_run(lang) or {}
    data = {
        **prev,
        "lang": lang,
        "state": state,
        "updated_at": _now(),
        **extra,
    }
    if "created_at" not in data:
        data["created_at"] = _now()
    ir.write_run(lang, data)
    return data


def get_run_status(lang: str) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise OrchestratorError(f"不支持的语言: {lang}")
    run = ir.read_run(lang) or {"lang": lang, "state": "INIT"}
    plan = ir.read_change_plan(lang)
    validation = ir.read_validation(lang)
    return {
        "lang": lang,
        "state": run.get("state", "INIT"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "error": run.get("error"),
        "auto_approve_plan": settings.auto_approve_plan,
        "plan_approved": bool((plan or {}).get("approved")),
        "plan_summary": (plan or {}).get("summary"),
        "task_count": len((plan or {}).get("tasks") or []),
        "validation_ok": (validation or {}).get("ok"),
        "repair_count": (validation or {}).get("repair_count", 0),
        "ir_dir": str(ir.ir_dir(lang)),
        "run": run,
        "change_plan": plan,
        "validation": validation,
        "spec": ir.read_spec(lang),
    }


async def run_analyze(lang: str, spec: str) -> dict[str, Any]:
    """Requirements → RepoIntel → Planner → AWAITING_APPROVAL（可自动批准）。"""
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise OrchestratorError(f"不支持的语言: {lang}")
    spec = spec.strip()
    if not spec:
        raise OrchestratorError("需求不能为空")

    root = settings.auto_code_dir(lang)
    root.mkdir(parents=True, exist_ok=True)
    docs_dir(lang).mkdir(parents=True, exist_ok=True)

    try:
        _set_run(lang, "INTEL", error=None)
        intel = await run_repo_intel(lang)
        structure_file = intel["structure_file"]
        baseline = (intel.get("codebase_ir") or {}).get("baseline") or {}

        _set_run(lang, "REQUIRE")
        req = await run_requirements(
            lang,
            spec,
            structure_md=structure_file["content"],
            baseline=baseline,
        )

        _set_run(lang, "PLAN")
        plan_result = await run_planner(lang)
        plan = plan_result["change_plan"]

        if settings.auto_approve_plan:
            plan["approved"] = True
            ir.write_change_plan(lang, plan)
            run = _set_run(
                lang,
                "AWAITING_APPROVAL",
                error=None,
                plan_approved=True,
                note="auto_approved",
            )
        else:
            run = _set_run(lang, "AWAITING_APPROVAL", plan_approved=False)

    except (RequirementsError, PlannerError) as e:
        _set_run(lang, "FAILED", error=str(e))
        raise OrchestratorError(str(e)) from e
    except Exception as e:
        _set_run(lang, "FAILED", error=str(e))
        raise OrchestratorError(str(e)) from e

    files: list[dict[str, str]] = [
        {
            "key": structure_file["key"],
            "title": structure_file["title"],
            "path": structure_file["path"],
            "content": structure_file["content"],
        }
    ]
    files.extend(req["files"])

    return {
        "lang": lang,
        "docs_root": str(docs_dir(lang)),
        "files": files,
        "run_state": run.get("state"),
        "plan_approved": bool(plan.get("approved")),
        "plan_summary": plan.get("summary"),
        "task_count": len(plan.get("tasks") or []),
    }


def confirm_plan(lang: str) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise OrchestratorError(f"不支持的语言: {lang}")
    plan = ir.read_change_plan(lang)
    if not plan:
        raise OrchestratorError("尚无 change_plan，请先调用 /agent/analyze")
    run = ir.read_run(lang) or {}
    if run.get("state") not in {"AWAITING_APPROVAL", "PLAN", "DONE", "FAILED", "CODE", "VALIDATE", "REVIEW"}:
        # 宽松：只要有 plan 就允许确认
        pass
    plan["approved"] = True
    ir.write_change_plan(lang, plan)
    _set_run(lang, "AWAITING_APPROVAL", plan_approved=True, error=None)
    return get_run_status(lang)


def _write_review(lang: str, codegen_result: dict[str, Any], validation: dict[str, Any]) -> dict[str, str]:
    plan = ir.read_change_plan(lang) or {}
    lines = [
        "# 变更报告（Review）",
        "",
        f"- 语言：`{lang}`",
        f"- 模式：从零生成",
        f"- 方案摘要：{plan.get('summary') or '（无）'}",
        f"- 生成文件数：{len(codegen_result.get('files') or [])}",
        f"- 校验通过：{'是' if validation.get('ok') else '否'}",
        f"- 修复次数：{validation.get('repair_count', 0)}",
        "",
        "## 端点",
        "",
    ]
    for ep in codegen_result.get("endpoints") or []:
        lines.append(f"- `{ep.get('method')} {ep.get('path')}` — {ep.get('description') or ''}")
    lines.append("")
    lines.append("## 文件清单")
    lines.append("")
    for f in codegen_result.get("files") or []:
        lines.append(f"- `{f}`")
    lines.append("")
    if validation.get("skipped"):
        lines.append("## 校验跳过")
        lines.append("")
        for s in validation["skipped"]:
            lines.append(f"- {s}")
        lines.append("")
    if validation.get("note"):
        lines.append(f"> {validation['note']}")
        lines.append("")
    body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    path = docs_dir(lang) / "06-review.md"
    path.write_text(body, encoding="utf-8", newline="\n")
    return {"key": "review", "title": "变更报告", "path": "docs/06-review.md", "content": body}


async def run_generate(
    lang: str,
    spec: str | None = None,
    *,
    use_docs: bool = True,
) -> dict[str, Any]:
    """Coder ⇄ Validator → Review。需 plan 已批准（或 AUTO_APPROVE）。"""
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise OrchestratorError(f"不支持的语言: {lang}")

    plan = ir.read_change_plan(lang)
    if use_docs:
        docs = read_docs(lang)
        if not docs.get("exists"):
            raise OrchestratorError("尚未生成需求文档，请先调用 /agent/analyze")
        if not plan:
            raise OrchestratorError("尚无 change_plan，请先调用 /agent/analyze")
        if not plan.get("approved"):
            raise OrchestratorError("change_plan 未批准：请 POST /agent/plan/confirm 或设置 AUTO_APPROVE_PLAN=true")

    max_repairs = max(0, int(settings.validate_max_repairs))
    repair_hints: str | None = None
    last_result: dict[str, Any] | None = None
    validation: dict[str, Any] = {"ok": False, "repair_count": 0}

    try:
        for attempt in range(max_repairs + 1):
            _set_run(lang, "CODE", repair_attempt=attempt, error=None)
            last_result = await run_coder(lang, spec, use_docs=use_docs, repair_hints=repair_hints)

            _set_run(lang, "VALIDATE", repair_attempt=attempt)
            validation = await run_validator(lang, repair_count=attempt)
            if validation.get("ok"):
                break
            if attempt >= max_repairs:
                _set_run(
                    lang,
                    "FAILED",
                    error=f"校验失败且已达最大修复次数 {max_repairs}",
                    validation_ok=False,
                )
                raise OrchestratorError(
                    f"校验失败且已达最大修复次数 {max_repairs}："
                    f"{(validation.get('repair_hints') or '')[:500]}"
                )
            repair_hints = validation.get("repair_hints") or "编译失败，请修复后重新生成完整工程。"

        assert last_result is not None
        _set_run(lang, "REVIEW")
        _write_review(lang, last_result, validation)
        _set_run(lang, "DONE", validation_ok=True, error=None)
        return {
            **last_result,
            "run_state": "DONE",
            "validation_ok": True,
            "repair_count": validation.get("repair_count", 0),
        }
    except CodegenError as e:
        _set_run(lang, "FAILED", error=str(e))
        raise OrchestratorError(str(e)) from e
    except OrchestratorError:
        raise
    except Exception as e:
        _set_run(lang, "FAILED", error=str(e))
        raise OrchestratorError(str(e)) from e


__all__ = [
    "OrchestratorError",
    "run_analyze",
    "run_generate",
    "confirm_plan",
    "get_run_status",
]
