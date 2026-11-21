from __future__ import annotations

import logging
from typing import Any

from backend.services import ir
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)


class PlannerError(RuntimeError):
    pass


def _project_exists(lang: str, codebase: dict[str, Any]) -> bool:
    """已有可识别工程时走增量，避免把「加删除接口」规划成整站重做。"""
    root = ir.docs_dir(lang).parent
    if lang == "java" and (root / "pom.xml").is_file():
        return True
    if lang == "go" and ((root / "go.mod").is_file() or (root / "main.go").is_file()):
        return True
    files = codebase.get("files") or codebase.get("controllers") or codebase.get("modules")
    return bool(files)


def _system_prompt(lang: str, *, incremental: bool) -> str:
    stack = (
        "Spring Boot Maven：controller/service/repository/entity、pom.xml、application.yml"
        if lang == "java"
        else "Go stdlib net/http：main.go、handler/service、go.mod"
    )
    if incremental:
        mode_rules = (
            "- 模式：incremental（在已有工程上迭代）。\n"
            "- 必须保留并扩展现有业务能力；禁止无故改成无关新系统。\n"
            "- 用户最新硬需求（如新增 DELETE 图书）必须出现在 apis 与 tasks 中。\n"
            "- tasks 描述「修改/新增哪些文件」，不要假装从零脚手架；files 用真实相对路径。\n"
            "- 若需求是增量接口，tasks 可 2～6 个，须含对应前后端验收（若 java）。\n"
        )
    else:
        mode_rules = (
            "- 模式：greenfield（从零生成）。\n"
            "- 列出将新建的模块/API/表。\n"
            "- tasks 按依赖排序，至少 3 个任务。\n"
        )
    fe_rules = (
        "- java：凡 apis 含业务写操作（POST/PATCH/PUT/DELETE），必须另有任务修改 frontend/ "
        "（如 frontend/src/api/client.ts、列表/详情 Vue），acceptance 含前端可点删除/提交。\n"
        "- 禁止把「不涉及前端」写入 risks 来回避配套 Vue。\n"
        if lang == "java"
        else ""
    )
    return (
        "你是技术方案与任务规划 Agent。根据需求 Spec、用户硬需求与代码库基线 IR，输出 JSON（不要 markdown 围栏）。\n"
        "Schema:\n"
        "{\n"
        '  "summary": "一句话方案摘要（必须点明本次用户硬需求）",\n'
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
        f"{mode_rules}"
        f"{fe_rules}"
        "- apis 至少含 GET /health；用户点名的 method+path 必须原样出现在 apis。\n"
        "- 最后一任务须含可运行验收（含 GET /health）。\n"
        "- 字段用中文简述即可。\n"
    )


def _fallback_plan(lang: str, spec: dict[str, Any] | None, *, incremental: bool) -> dict[str, Any]:
    goals = (spec or {}).get("goals") or ["实现核心 API"]
    prefix = "增量修改" if incremental else "从零生成"
    return {
        "summary": f"{prefix} {lang} 后端：{goals[0] if goals else '核心功能'}",
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
                "title": "工程脚手架" if not incremental else "定位并修改目标模块",
                "deps": [],
                "files": ["pom.xml or go.mod", "main entry", "config"],
                "acceptance": ["构建文件齐全"] if not incremental else ["改动编译通过"],
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
    incremental = _project_exists(lang, codebase)
    docs = ir.docs_dir(lang)
    doc_bits: list[str] = []
    for name in ("00-input.md", "01-requirements.md", "02-architecture.md", "03-database.md", "04-api.md"):
        p = docs / name
        if p.is_file():
            doc_bits.append(f"### {name}\n{p.read_text(encoding='utf-8')[:4000]}")

    mode = "incremental" if incremental else "greenfield"
    user_msg = (
        f"lang={lang}\nmode={mode}\n\n"
        f"## spec.json\n{spec}\n\n"
        f"## codebase_ir.json\n{codebase}\n\n"
        f"## docs 摘要\n" + "\n\n".join(doc_bits)
    )

    try:
        raw = await chat_completion(system=_system_prompt(lang, incremental=incremental), user=user_msg)
        data = extract_json_object(raw)
    except (LlmError, ValueError) as e:
        logger.warning("Planner LLM 失败，使用回退计划: %s", e)
        data = _fallback_plan(lang, spec, incremental=incremental)

    if not isinstance(data.get("tasks"), list) or not data["tasks"]:
        data = _fallback_plan(lang, spec, incremental=incremental)

    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    apis = data.get("apis") if isinstance(data.get("apis"), list) else []
    # java：接口有写操作但 tasks 未含 frontend/ 时补一条，避免只改后端
    if lang == "java":
        write_apis = [
            a
            for a in apis
            if isinstance(a, dict) and str(a.get("method") or "").upper() in {"POST", "PUT", "PATCH", "DELETE"}
        ]
        has_fe_task = any(
            isinstance(t, dict)
            and any(str(f).replace("\\", "/").startswith("frontend/") for f in (t.get("files") or []))
            for t in tasks
        )
        if write_apis and not has_fe_task:
            tasks = list(tasks) + [
                {
                    "id": f"T{len(tasks) + 1}",
                    "title": "配套 Vue 前端：暴露新增/变更接口操作",
                    "deps": [str(tasks[-1].get("id") or "T1")] if tasks and isinstance(tasks[-1], dict) else [],
                    "files": [
                        "frontend/src/api/client.ts",
                        "frontend/src/views/BookListView.vue",
                        "frontend/src/views/BookDetailView.vue",
                    ],
                    "acceptance": [
                        "前端可选择目标并调用对应写接口（含 DELETE 若存在）",
                        "错误展示后端 code/message",
                    ],
                }
            ]

    plan = {
        "lang": lang,
        "mode": mode,
        "approved": False,
        "summary": str(data.get("summary") or ""),
        "modules": data.get("modules") if isinstance(data.get("modules"), list) else [],
        "apis": apis,
        "data_model": data.get("data_model") if isinstance(data.get("data_model"), list) else [],
        "tasks": tasks,
        "risks": data.get("risks") if isinstance(data.get("risks"), list) else [],
    }
    path = ir.write_change_plan(lang, plan)
    logger.info("Planner 完成 lang=%s mode=%s tasks=%d", lang, mode, len(plan["tasks"]))
    return {"change_plan": plan, "ir_path": str(path)}
