from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.services import ir
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion

logger = logging.getLogger(__name__)

MAX_TURNS = 12  # 用户发言上限
ELICIT_STATUSES = frozenset({"drafting", "concluded", "confirmed"})


class ElicitorError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session(lang: str) -> dict[str, Any]:
    return {
        "session_id": uuid.uuid4().hex[:12],
        "lang": lang,
        "status": "drafting",
        "messages": [],
        "conclusion": None,
        "created_at": _now(),
        "updated_at": _now(),
        "confirmed_at": None,
    }


def _user_turn_count(messages: list[dict[str, Any]]) -> int:
    return sum(1 for m in messages if m.get("role") == "user")


def get_or_create_elicitation(lang: str) -> dict[str, Any]:
    data = ir.read_elicitation(lang)
    if data and isinstance(data.get("messages"), list):
        data.setdefault("status", "drafting")
        data.setdefault("lang", lang)
        return data
    data = _new_session(lang)
    ir.write_elicitation(lang, data)
    return data


def _archive_if_needed(lang: str, data: dict[str, Any]) -> None:
    messages = data.get("messages") or []
    if not messages:
        return
    sid = str(data.get("session_id") or uuid.uuid4().hex[:12])
    snapshot = dict(data)
    snapshot["session_id"] = sid
    ir.write_session(lang, sid, snapshot)


def conclusion_to_spec_text(conclusion: dict[str, Any]) -> str:
    goals = conclusion.get("goals") or []
    scope = conclusion.get("scope") or []
    out_of_scope = conclusion.get("out_of_scope") or []
    nfr = conclusion.get("nfr") or []
    open_q = conclusion.get("open_questions") or []
    lines = [
        "# 需求结论（澄清确认）",
        "",
        "## 摘要",
        str(conclusion.get("summary") or "").strip() or "（无）",
        "",
        "## 目标",
    ]
    lines.extend([f"- {g}" for g in goals] if goals else ["- （无）"])
    lines.extend(["", "## 范围"])
    lines.extend([f"- {s}" for s in scope] if scope else ["- （无）"])
    lines.extend(["", "## 不在范围"])
    lines.extend([f"- {s}" for s in out_of_scope] if out_of_scope else ["- （无）"])
    lines.extend(["", "## 非功能"])
    lines.extend([f"- {s}" for s in nfr] if nfr else ["- （无）"])
    if open_q:
        lines.extend(["", "## 待决问题（确认时已接受）"])
        lines.extend([f"- {q}" for q in open_q])
    lines.extend(
        [
            "",
            "## 硬约束",
            "- 必须提供 GET /health",
            "- 面向从零生成后端 API",
        ]
    )
    return "\n".join(lines) + "\n"


def _chat_system(lang: str) -> str:
    stack = "Java/Spring Boot" if lang == "java" else "Go net/http"
    return (
        "你是需求澄清助手（单窗）。只澄清业务需求，禁止输出代码或文件路径清单。\n"
        f"目标栈：{stack}（从零生成）。\n"
        "输出 JSON（不要 markdown 代码围栏）：\n"
        "{\n"
        '  "reply": "对用户的下一问或确认（中文，简洁）",\n'
        '  "ready_to_conclude": false\n'
        "}\n"
        "规则：\n"
        "- 每次只问 1～2 个关键问题（目标、范围、实体、接口、非功能）。\n"
        "- 信息已够时可 ready_to_conclude=true，并在 reply 中提示用户可点「总结」。\n"
        "- 不要一次抛出长问卷。\n"
        "- 不要编写或草拟代码。\n"
    )


def _conclude_system(lang: str) -> str:
    stack = "Java/Spring Boot" if lang == "java" else "Go net/http"
    return (
        "你是需求澄清总结器。根据对话整理结构化结论，禁止输出代码。\n"
        f"目标栈：{stack}。\n"
        "输出 JSON（不要 markdown 代码围栏）：\n"
        "{\n"
        '  "summary": "一段话摘要",\n'
        '  "goals": ["业务目标"],\n'
        '  "scope": ["范围内功能"],\n'
        '  "out_of_scope": ["明确不做"],\n'
        '  "nfr": ["非功能要求"],\n'
        '  "open_questions": ["仍不清楚但可后续假设的问题"]\n'
        "}\n"
        "规则：信息不足时做合理假设并写入 open_questions；scope 至少 2 条；必须隐含可提供 GET /health。\n"
    )


async def send_message(lang: str, content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ElicitorError("消息不能为空")

    data = get_or_create_elicitation(lang)
    status = data.get("status") or "drafting"
    if status == "confirmed":
        raise ElicitorError("当前会话已确认，请新建会话后再聊")

    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if _user_turn_count(messages) >= MAX_TURNS:
        raise ElicitorError(f"已达最大澄清轮数 {MAX_TURNS}，请先「总结」或新建会话")

    messages.append({"role": "user", "content": text, "at": _now()})

    history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
    user_msg = f"## 对话\n{history}\n\n请给出下一句澄清回复（JSON）。"
    try:
        raw = await chat_completion(system=_chat_system(lang), user=user_msg)
        obj = extract_json_object(raw)
        reply = str(obj.get("reply") or "").strip()
        ready = bool(obj.get("ready_to_conclude"))
    except (LlmError, ValueError) as e:
        logger.warning("elicit message LLM 失败: %s", e)
        reply = "收到。请补充：核心业务对象、主要操作（增删改查）、以及必须有的接口？"
        ready = _user_turn_count(messages) >= 3

    if not reply:
        reply = "请再描述一下你希望系统完成的核心能力。"

    messages.append({"role": "assistant", "content": reply, "at": _now()})
    data["messages"] = messages
    data["status"] = "drafting"
    data["conclusion"] = None
    data["confirmed_at"] = None
    data["updated_at"] = _now()
    ir.write_elicitation(lang, data)
    return {
        "elicitation": data,
        "reply": reply,
        "ready_to_conclude": ready,
        "user_turns": _user_turn_count(messages),
        "max_turns": MAX_TURNS,
    }


async def conclude(lang: str) -> dict[str, Any]:
    data = get_or_create_elicitation(lang)
    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if not messages:
        raise ElicitorError("尚无对话，无法总结")
    if data.get("status") == "confirmed":
        raise ElicitorError("当前会话已确认，请新建会话")

    history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
    user_msg = f"## 对话\n{history}\n\n请输出结论 JSON。"
    try:
        raw = await chat_completion(system=_conclude_system(lang), user=user_msg)
        obj = extract_json_object(raw)
    except (LlmError, ValueError) as e:
        raise ElicitorError(f"总结失败: {e}") from e

    conclusion = {
        "summary": str(obj.get("summary") or "").strip(),
        "goals": [str(x) for x in (obj.get("goals") or []) if str(x).strip()],
        "scope": [str(x) for x in (obj.get("scope") or []) if str(x).strip()],
        "out_of_scope": [str(x) for x in (obj.get("out_of_scope") or []) if str(x).strip()],
        "nfr": [str(x) for x in (obj.get("nfr") or []) if str(x).strip()],
        "open_questions": [str(x) for x in (obj.get("open_questions") or []) if str(x).strip()],
    }
    if not conclusion["summary"]:
        conclusion["summary"] = "（模型未给出摘要，请编辑后确认）"
    if len(conclusion["scope"]) < 1:
        conclusion["scope"] = ["提供基础 REST API 与 GET /health"]

    data["conclusion"] = conclusion
    data["status"] = "concluded"
    data["updated_at"] = _now()
    ir.write_elicitation(lang, data)
    return {"elicitation": data}


async def confirm(lang: str, conclusion: dict[str, Any] | None = None) -> dict[str, Any]:
    """确认结论 → 归档会话 → 调用现有 analyze 写入 docs/spec。"""
    from backend.services.analyze import AnalyzeError, analyze_requirements

    data = get_or_create_elicitation(lang)
    if data.get("status") == "confirmed" and not conclusion:
        raise ElicitorError("已确认过，请新建会话或恢复历史后再确认")

    base = data.get("conclusion") if isinstance(data.get("conclusion"), dict) else {}
    if conclusion:
        merged = {
            "summary": str(conclusion.get("summary", base.get("summary") or "")).strip(),
            "goals": [str(x) for x in (conclusion.get("goals") or base.get("goals") or []) if str(x).strip()],
            "scope": [str(x) for x in (conclusion.get("scope") or base.get("scope") or []) if str(x).strip()],
            "out_of_scope": [
                str(x)
                for x in (conclusion.get("out_of_scope") or base.get("out_of_scope") or [])
                if str(x).strip()
            ],
            "nfr": [str(x) for x in (conclusion.get("nfr") or base.get("nfr") or []) if str(x).strip()],
            "open_questions": [
                str(x)
                for x in (conclusion.get("open_questions") or base.get("open_questions") or [])
                if str(x).strip()
            ],
        }
    else:
        merged = base if isinstance(base, dict) else {}

    if not merged or not str(merged.get("summary") or "").strip():
        raise ElicitorError("没有可确认的结论，请先「总结」")

    data["conclusion"] = merged
    data["status"] = "confirmed"
    data["confirmed_at"] = _now()
    data["updated_at"] = _now()
    ir.write_elicitation(lang, data)
    _archive_if_needed(lang, data)

    spec_text = conclusion_to_spec_text(merged)
    try:
        analyze_result = await analyze_requirements(lang, spec_text)
    except AnalyzeError as e:
        # 回滚确认状态，便于重试
        data["status"] = "concluded"
        data["confirmed_at"] = None
        data["updated_at"] = _now()
        ir.write_elicitation(lang, data)
        raise ElicitorError(f"确认后分析失败: {e}") from e

    return {"elicitation": data, "analyze": analyze_result}


def new_session(lang: str) -> dict[str, Any]:
    current = ir.read_elicitation(lang)
    if current and (current.get("messages") or current.get("conclusion")):
        _archive_if_needed(lang, current)
    data = _new_session(lang)
    ir.write_elicitation(lang, data)
    return {"elicitation": data}


def restore_session(lang: str, session_id: str) -> dict[str, Any]:
    snap = ir.read_session(lang, session_id)
    if not snap:
        raise ElicitorError(f"会话不存在: {session_id}")
    current = ir.read_elicitation(lang)
    if current and (current.get("messages") or current.get("conclusion")):
        if current.get("session_id") != snap.get("session_id"):
            _archive_if_needed(lang, current)
    restored = dict(snap)
    restored["lang"] = lang
    restored["updated_at"] = _now()
    # 恢复后允许继续编辑：已确认的变为 concluded，便于再确认
    if restored.get("status") == "confirmed":
        restored["status"] = "concluded"
        restored["confirmed_at"] = None
    ir.write_elicitation(lang, restored)
    return {"elicitation": restored}


def list_history(lang: str) -> dict[str, Any]:
    return {"lang": lang, "sessions": ir.list_sessions(lang)}
