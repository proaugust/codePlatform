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
) -> dict[str, Any]:
    """调用代码生成引擎；注入 change_plan 与可选修复提示。"""
    plan = ir.read_change_plan(lang)
    plan_context = ""
    if plan:
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
        result = await generate_project(lang, extra or None, use_docs=use_docs)
    except CodegenError:
        raise

    logger.info("Coder 完成 lang=%s files=%d", lang, len(result.get("files") or []))
    return result
