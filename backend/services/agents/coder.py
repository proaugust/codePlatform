from __future__ import annotations

import logging
from typing import Any

from backend.services import ir
from backend.services.codegen import CodegenError, generate_project

logger = logging.getLogger(__name__)


async def run_coder(
    lang: str,
    spec: str | None = None,
    *,
    use_docs: bool = True,
    repair_hints: str | None = None,
    repair_paths: list[str] | None = None,
) -> dict[str, Any]:
    """调用代码生成引擎；注入 change_plan 与可选修复提示。"""
    plan = ir.read_change_plan(lang)
    repairing = bool(repair_hints or repair_paths)
    plan_context = ""
    if plan:
        if repairing:
            # 修复轮：只带摘要+API，避免把整份 tasks 再喂一遍
            plan_context = (
                "\n\n---\n\n# Change Plan (compact)\n\n"
                f"summary: {plan.get('summary')}\n"
                f"apis: {plan.get('apis')}\n"
            )
        else:
            plan_context = (
                "\n\n---\n\n# Change Plan (approved tasks)\n\n"
                f"summary: {plan.get('summary')}\n"
                f"modules: {plan.get('modules')}\n"
                f"apis: {plan.get('apis')}\n"
                f"tasks: {plan.get('tasks')}\n"
            )

    extra = (spec or "").strip()
    if plan_context:
        extra = (extra + plan_context) if extra else plan_context.strip()
    if repair_hints:
        extra = (extra or "") + "\n\n---\n\n# Validation repair hints\n\n" + repair_hints

    try:
        result = await generate_project(
            lang,
            extra or None,
            use_docs=use_docs,
            repair_paths=list(repair_paths) if repair_paths else None,
        )
    except CodegenError:
        raise

    logger.info(
        "Coder 完成 lang=%s files=%d repair=%s",
        lang,
        len(result.get("files") or []),
        bool(repair_paths),
    )
    return result
