from __future__ import annotations

import logging
from typing import Any

from backend.services import ir
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)

DOC_KEYS: tuple[tuple[str, str, str], ...] = (
    ("requirements", "01-requirements.md", "总需求"),
    ("architecture", "02-architecture.md", "架构"),
    ("database", "03-database.md", "数据库表"),
    ("api", "04-api.md", "接口"),
)


class RequirementsError(RuntimeError):
    pass


def _system_prompt(lang: str) -> str:
    stack = (
        "面向后续 Spring Boot（Maven / JPA / Controller-Service-Repository）实现，表结构与接口要可落地。"
        if lang == "java"
        else "面向后续 Go 标准库 net/http 实现，表结构与接口要可落地。"
    )
    return (
        "你是需求分析 Agent（从零生成场景）。先阅读「目标栈基线/工程结构」，再结合用户原始需求，"
        "输出一份 JSON（不要 markdown 代码围栏）。\n"
        "Schema:\n"
        "{\n"
        '  "requirements": "Markdown：总需求（背景、目标、范围、非功能）",\n'
        '  "architecture": "Markdown：架构（分层、模块、技术选型、部署）",\n'
        '  "database": "Markdown：数据库表（表名、字段、类型、约束、关系）",\n'
        '  "api": "Markdown：接口清单（方法、路径、请求/响应、错误码）",\n'
        '  "spec": {\n'
        '    "goals": ["业务目标"],\n'
        '    "scope": "功能边界",\n'
        '    "inputs": ["输入"],\n'
        '    "outputs": ["输出"],\n'
        '    "constraints": ["约束"],\n'
        '    "assumptions": ["假设"],\n'
        '    "acceptance": ["验收标准"]\n'
        "  }\n"
        "}\n"
        "规则：\n"
        "- requirements/architecture/database/api 必须是完整中文 Markdown 正文。\n"
        "- spec 各字段用简洁中文；acceptance 至少 2 条可验证标准。\n"
        "- 信息不足时做合理假设，并在文中与 assumptions 标明。\n"
        "- 接口至少包含 GET /health。\n"
        f"- {stack}\n"
        "- 从零生成：按基线约定设计，不要假设已有业务代码。\n"
        "- 不要输出工程结构正文。\n"
    )


async def run_requirements(
    lang: str,
    spec: str,
    *,
    structure_md: str,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = ir.docs_dir(lang)
    out.mkdir(parents=True, exist_ok=True)
    (out / "00-input.md").write_text(spec.strip() + "\n", encoding="utf-8", newline="\n")

    baseline_txt = ""
    if baseline:
        baseline_txt = (
            f"## 目标栈基线\n\n"
            f"- stack: {baseline.get('stack')}\n"
            f"- port: {baseline.get('port')}\n"
            f"- conventions: {baseline.get('conventions')}\n\n"
        )

    user_msg = (
        f"目标技术栈语言: {lang}\n"
        f"代码根目录: auto_code/{lang}\n"
        f"场景: 从零生成\n\n"
        f"{baseline_txt}"
        f"## 现有工程结构（系统扫描）\n\n{structure_md}\n"
        f"## 用户原始需求\n\n{spec}\n"
    )

    try:
        raw = await chat_completion(system=_system_prompt(lang), user=user_msg)
    except LlmError as e:
        raise RequirementsError(str(e)) from e

    try:
        data = extract_json_object(raw)
    except ValueError as e:
        raise RequirementsError(str(e)) from e

    files: list[dict[str, str]] = []
    for key, filename, title in DOC_KEYS:
        content = data.get(key)
        if not isinstance(content, str) or not content.strip():
            raise RequirementsError(f"分析结果缺少字段: {key}（{title}）")
        path = out / filename
        body = content if content.endswith("\n") else content + "\n"
        path.write_text(body, encoding="utf-8", newline="\n")
        files.append({"key": key, "title": title, "path": f"docs/{filename}", "content": body})

    spec_obj = data.get("spec")
    if not isinstance(spec_obj, dict):
        spec_obj = {
            "goals": ["实现用户需求中的核心功能"],
            "scope": "后端 API（从零生成）",
            "inputs": ["用户自然语言需求"],
            "outputs": ["可运行后端工程", "需求文档"],
            "constraints": [f"目标语言 {lang}"],
            "assumptions": ["信息不足处已在文档中标注假设"],
            "acceptance": ["GET /health 返回 ok", "文档四件套齐全"],
        }
    spec_payload = {
        "lang": lang,
        "raw_spec": spec.strip(),
        "mode": "greenfield",
        **{k: spec_obj.get(k) for k in ("goals", "scope", "inputs", "outputs", "constraints", "assumptions", "acceptance")},
    }
    ir_path = ir.write_spec(lang, spec_payload)
    logger.info("Requirements 完成 lang=%s ir=%s", lang, ir_path)
    return {"files": files, "spec": spec_payload, "ir_path": str(ir_path)}
