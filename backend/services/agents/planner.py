from __future__ import annotations

import logging
from typing import Any

from backend.services import ir
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)


class PlannerError(RuntimeError):
    pass


def _system_prompt(lang: str) -> str:
    stack = (
        "Spring Boot Maven：controller/service/repository/entity、pom.xml、application.yml"
        if lang == "java"
        else "Go stdlib net/http：main.go、handler/service、go.mod"
    )
    return (
        "你是技术方案与任务规划 Agent（从零生成）。根据需求 Spec 与代码库基线 IR，输出 JSON（不要 markdown 围栏）。\n"
        "Schema:\n"
        "{\n"
        '  "summary": "一句话方案摘要",\n'
        '  "modules": [{"name": "模块名", "responsibility": "职责"}],\n'
        '  "apis": [{"method": "GET", "path": "/health", "description": "..."}],\n'
        '  "data_model": [{"name": "表或实体", "fields": ["id", "..."]}],\n'
        '  "tasks": [\n'
        "    {\n"
        '      "id": "T1",\n'
        '      "title": "任务标题",\n'
        '      "deps": [],\n'
        '      "files": ["相对路径提示"],\n'
        '      "acceptance": ["可验证验收条件"]\n'
        "    }\n"
        "  ],\n"
        '  "risks": ["风险或边界"]\n'
        "}\n"
        "规则：\n"
        f"- 技术栈：{stack}\n"
        "- 从零生成：列出将新建的模块/API/表，不要描述「修改已有」。\n"
        "- tasks 按依赖排序，至少 3 个任务，最后一任务须含 GET /health 验收。\n"
        "- apis 至少含 GET /health。\n"
        "- 字段用中文简述即可。\n"
    )


def _fallback_plan(lang: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    goals = (spec or {}).get("goals") or ["实现核心 API"]
    return {
        "summary": f"从零生成 {lang} 后端：{goals[0] if goals else '核心功能'}",
        "modules": [
            {"name": "bootstrap", "responsibility": "工程入口与配置"},
            {"name": "api", "responsibility": "HTTP 接口层"},
            {"name": "domain", "responsibility": "业务与数据访问"},
        ],
        "apis": [{"method": "GET", "path": "/health", "description": "健康检查"}],
        "data_model": [],
        "tasks": [
            {
                "id": "T1",
                "title": "工程脚手架",
                "deps": [],
                "files": ["pom.xml or go.mod", "main entry", "config"],
                "acceptance": ["构建文件齐全"],
            },
            {
                "id": "T2",
                "title": "领域与数据",
                "deps": ["T1"],
                "files": [],
                "acceptance": ["按需求文档建模"],
            },
            {
                "id": "T3",
                "title": "API 与健康检查",
                "deps": ["T2"],
                "files": [],
                "acceptance": ["GET /health 返回 ok"],
            },
        ],
        "risks": ["LLM 规划失败，使用回退计划"],
    }


async def run_planner(lang: str) -> dict[str, Any]:
    spec = ir.read_spec(lang) or {}
    codebase = ir.read_codebase_ir(lang) or {}
    docs = ir.docs_dir(lang)
    doc_bits: list[str] = []
    for name in ("01-requirements.md", "02-architecture.md", "03-database.md", "04-api.md"):
        p = docs / name
        if p.is_file():
            doc_bits.append(f"### {name}\n{p.read_text(encoding='utf-8')[:4000]}")

    user_msg = (
        f"lang={lang}\nmode=greenfield\n\n"
        f"## spec.json\n{spec}\n\n"
        f"## codebase_ir.json\n{codebase}\n\n"
        f"## docs 摘要\n" + "\n\n".join(doc_bits)
    )

    try:
        raw = await chat_completion(system=_system_prompt(lang), user=user_msg)
        data = extract_json_object(raw)
    except (LlmError, ValueError) as e:
        logger.warning("Planner LLM 失败，使用回退计划: %s", e)
        data = _fallback_plan(lang, spec)

    if not isinstance(data.get("tasks"), list) or not data["tasks"]:
        data = _fallback_plan(lang, spec)

    plan = {
        "lang": lang,
        "mode": "greenfield",
        "approved": False,
        "summary": str(data.get("summary") or ""),
        "modules": data.get("modules") if isinstance(data.get("modules"), list) else [],
        "apis": data.get("apis") if isinstance(data.get("apis"), list) else [],
        "data_model": data.get("data_model") if isinstance(data.get("data_model"), list) else [],
        "tasks": data.get("tasks") if isinstance(data.get("tasks"), list) else [],
        "risks": data.get("risks") if isinstance(data.get("risks"), list) else [],
    }
    path = ir.write_change_plan(lang, plan)
    logger.info("Planner 完成 lang=%s tasks=%d", lang, len(plan["tasks"]))
    return {"change_plan": plan, "ir_path": str(path)}
