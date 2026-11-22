from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.services import ir
from backend.services.jsonutil import extract_json_object
from backend.services.llm import LlmError, chat_completion
from backend.services.platform_prefs import get_max_turns

logger = logging.getLogger(__name__)

RECENT_KEEP = 6  # 压缩后保留的最近原文条数（约 3 轮）
MAX_CHARS = 20000  # 原文过长时强制总结压缩
ELICIT_STATUSES = frozenset({"drafting", "planned", "closed", "concluded", "confirmed"})

# 空消息 / 纯标点 / 常见口头禅：不调 LLM
_USELESS_EXACT = frozenset(
    {
        "嗯",
        "嗯嗯",
        "啊",
        "哦",
        "呃",
        "额",
        "哈",
        "哈哈",
        "嘿嘿",
        "嗨",
        "好",
        "好的",
        "可以",
        "行",
        "是",
        "是的",
        "对",
        "对的",
        "收到",
        "谢谢",
        "感谢",
        "在吗",
        "你好",
        "您好",
        "hello",
        "hi",
        "hey",
        "ok",
        "okay",
        "yes",
        "no",
        "y",
        "n",
        "thx",
        "thanks",
        "test",
        "测试",
        "123",
        "…",
        "...",
        "。。。",
    }
)
_USELESS_RE = re.compile(
    r"^(?:嗯+|啊+|哦+|呃+|额+|哈+|嘿+|嗨+|好的*|ok+|okay|yes+|no+|谢谢+|感谢+|…+|\.+|。+|！+|!+|？+|\?+|～+|~+)$",
    re.IGNORECASE,
)
_HAS_SUBSTANCE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def _is_useless_message(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t) <= 1:
        return True
    if not _HAS_SUBSTANCE.search(t):
        return True
    low = t.lower()
    if low in _USELESS_EXACT or t in _USELESS_EXACT:
        return True
    if _USELESS_RE.fullmatch(t):
        return True
    # 过短且无明显中文词/英文词
    if len(t) < 4 and not re.search(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", t):
        return True
    return False


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
        "rolling_summary": "",
        "plan_ready": False,
        "last_plan": None,
        "created_at": _now(),
        "updated_at": _now(),
        "confirmed_at": None,
        "closed_at": None,
    }


def _user_turn_count(messages: list[dict[str, Any]]) -> int:
    return sum(1 for m in messages if m.get("role") == "user")


def _messages_chars(messages: list[dict[str, Any]]) -> int:
    return sum(len(str(m.get("content") or "")) for m in messages)


def _normalize_session(data: dict[str, Any], lang: str) -> dict[str, Any]:
    data.setdefault("status", "drafting")
    data.setdefault("lang", lang)
    data.setdefault("messages", [])
    data.setdefault("rolling_summary", "")
    data.setdefault("plan_ready", False)
    data.setdefault("last_plan", None)
    data.setdefault("closed_at", None)
    # 旧 confirmed 不再锁死：视为已有计划，可继续聊/再计划/再执行
    if data.get("status") == "confirmed":
        data["status"] = "planned"
        data["plan_ready"] = True
        data["confirmed_at"] = None
    if data.get("status") == "concluded" and data.get("conclusion"):
        # 有结论但未跑计划管线时，仍可聊；执行需再点「分析计划」
        pass
    return data


def get_or_create_elicitation(lang: str) -> dict[str, Any]:
    data = ir.read_elicitation(lang)
    if data and isinstance(data.get("messages"), list):
        return _normalize_session(data, lang)
    data = _new_session(lang)
    ir.write_elicitation(lang, data)
    return data


def _archive_if_needed(lang: str, data: dict[str, Any]) -> None:
    messages = data.get("messages") or []
    summary = str(data.get("rolling_summary") or "").strip()
    conclusion = data.get("conclusion") if isinstance(data.get("conclusion"), dict) else None
    if not messages and not summary and not conclusion:
        return
    sid = str(data.get("session_id") or uuid.uuid4().hex[:12])
    snapshot = dict(data)
    snapshot["session_id"] = sid
    ir.write_session(lang, sid, snapshot)


def _latest_user_directives(data: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    """提取最近用户原话，作为计划/生成不可忽略的硬需求。"""
    if not data:
        return []
    out: list[str] = []
    for m in reversed(list(data.get("messages") or [])):
        if m.get("role") != "user":
            continue
        text = str(m.get("content") or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    out.reverse()
    return out


def conclusion_to_chat_text(conclusion: dict[str, Any], *, task_count: int = 0) -> str:
    """聊天气泡：只留一两句摘要，结构化字段仍写入 docs，不在此展示。"""
    _ = task_count
    summary = str(conclusion.get("summary") or "").strip() or "（见文档）"
    return f"计划已更新：{summary}\n确认无误后可点「执行生成」写代码（不会自动启动进程）。"


def conclusion_to_spec_text(
    conclusion: dict[str, Any],
    *,
    rolling_summary: str = "",
    user_directives: list[str] | None = None,
) -> str:
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
    if user_directives:
        lines.extend(["", "## 用户硬需求（最高优先级，必须体现在 docs/计划/代码中）"])
        lines.extend([f"- {d}" for d in user_directives])
    if rolling_summary.strip():
        lines.extend(["", "## 会话滚动摘要", rolling_summary.strip()])
    lines.extend(
        [
            "",
            "## 硬约束",
            "- 必须提供 GET /health",
            "- 若工程已存在：默认增量修改，禁止无故改成无关新业务系统",
            "- 用户硬需求中的接口（如 DELETE 图书）必须出现在 API 文档与实现中",
        ]
    )
    return "\n".join(lines) + "\n"


def _chat_system(lang: str) -> str:
    stack = "Java/Spring Boot" if lang == "java" else "Go net/http"
    return (
        "你是需求澄清助手（单窗）。只澄清业务需求，禁止输出代码或文件路径清单。\n"
        f"目标栈：{stack}（可从零生成，也可基于已有工程迭代）。\n"
        "输出 JSON（不要 markdown 代码围栏）：\n"
        "{\n"
        '  "reply": "对用户的下一问或确认（中文，简洁）",\n'
        '  "ready_to_plan": false\n'
        "}\n"
        "规则：\n"
        "- 每次只问 1～2 个关键问题（目标、范围、实体、接口、非功能）。\n"
        "- 信息已够时可 ready_to_plan=true，并在 reply 中提示用户可点「分析计划」。\n"
        "- 不要一次抛出长问卷。\n"
        "- 不要编写或草拟代码。\n"
    )


def _conclude_system(lang: str) -> str:
    stack = "Java/Spring Boot" if lang == "java" else "Go net/http"
    fe_rule = (
        "- java 目标：接口变更（含 DELETE/POST/PATCH）默认须同步配套 Vue 前端操作；"
        "禁止在 out_of_scope 写「不涉及前端」若用户提到前端/页面/选择删除等。\n"
        if lang == "java"
        else "- 除非用户明确只要后端，否则不要把前端写进 out_of_scope。\n"
    )
    return (
        "你是需求澄清总结器。根据对话与历史摘要整理结构化结论，禁止输出代码。\n"
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
        "规则：\n"
        "- 最近一条用户原话优先级最高：summary/goals/scope 必须直接体现它（例如「增加删除图书接口」）。\n"
        "- 禁止用更早的滚动摘要覆盖/替换用户最新明确需求。\n"
        "- 若已有图书等业务工程，默认增量：补接口/前端操作，不要改成无关新系统。\n"
        f"{fe_rule}"
        "- 信息不足时做合理假设并写入 open_questions；scope 至少 2 条；必须隐含可提供 GET /health。\n"
    )


def _rollup_system() -> str:
    return (
        "你是会话记忆压缩器。把历史对话压缩成一段中文滚动摘要，保留：目标、范围、"
        "已确认决策、待决问题、与代码改动相关的约定。禁止输出代码。\n"
        "输出 JSON：{\"rolling_summary\": \"...\"}\n"
    )


def _context_block(data: dict[str, Any]) -> str:
    parts: list[str] = []
    directives = _latest_user_directives(data, limit=3)
    if directives:
        parts.append("## 用户硬需求（最高优先级）\n" + "\n".join(f"- {d}" for d in directives))
    summary = str(data.get("rolling_summary") or "").strip()
    if summary:
        parts.append(f"## 历史滚动摘要\n{summary}")
    messages = list(data.get("messages") or [])
    if messages:
        history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        parts.append(f"## 最近对话\n{history}")
    return "\n\n".join(parts) if parts else "（尚无对话）"


def _parse_conclusion(obj: dict[str, Any]) -> dict[str, Any]:
    conclusion = {
        "summary": str(obj.get("summary") or "").strip(),
        "goals": [str(x) for x in (obj.get("goals") or []) if str(x).strip()],
        "scope": [str(x) for x in (obj.get("scope") or []) if str(x).strip()],
        "out_of_scope": [str(x) for x in (obj.get("out_of_scope") or []) if str(x).strip()],
        "nfr": [str(x) for x in (obj.get("nfr") or []) if str(x).strip()],
        "open_questions": [str(x) for x in (obj.get("open_questions") or []) if str(x).strip()],
    }
    if not conclusion["summary"]:
        conclusion["summary"] = "（模型未给出摘要，请补充需求后再次分析计划）"
    if len(conclusion["scope"]) < 1:
        conclusion["scope"] = ["提供基础 REST API 与 GET /health"]
    # 范围已含前端时，去掉 out_of_scope 里的「不涉及前端」
    scope_text = " ".join(conclusion["scope"]) + conclusion["summary"]
    if any(k in scope_text for k in ("前端", "Vue", "页面")):
        conclusion["out_of_scope"] = [
            x
            for x in conclusion["out_of_scope"]
            if "不涉及前端" not in x and "不做前端" not in x and "不含前端" not in x
        ]
    return conclusion


def _merge_conclusion(
    base: dict[str, Any] | None,
    override: dict[str, Any] | None,
) -> dict[str, Any]:
    base = base if isinstance(base, dict) else {}
    if not override:
        return dict(base)
    return {
        "summary": str(override.get("summary", base.get("summary") or "")).strip(),
        "goals": [str(x) for x in (override.get("goals") or base.get("goals") or []) if str(x).strip()],
        "scope": [str(x) for x in (override.get("scope") or base.get("scope") or []) if str(x).strip()],
        "out_of_scope": [
            str(x) for x in (override.get("out_of_scope") or base.get("out_of_scope") or []) if str(x).strip()
        ],
        "nfr": [str(x) for x in (override.get("nfr") or base.get("nfr") or []) if str(x).strip()],
        "open_questions": [
            str(x)
            for x in (override.get("open_questions") or base.get("open_questions") or [])
            if str(x).strip()
        ],
    }


async def _compress_messages(data: dict[str, Any]) -> None:
    """把较旧原文并入 rolling_summary，只留 recent。"""
    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if len(messages) <= RECENT_KEEP and _messages_chars(messages) < MAX_CHARS:
        return

    older = messages[:-RECENT_KEEP] if len(messages) > RECENT_KEEP else messages
    recent = messages[-RECENT_KEEP:] if len(messages) > RECENT_KEEP else []
    prev = str(data.get("rolling_summary") or "").strip()
    older_text = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in older)
    user_msg = (
        f"## 已有滚动摘要\n{prev or '（无）'}\n\n"
        f"## 待压缩对话\n{older_text}\n\n请输出压缩后的 rolling_summary JSON。"
    )
    try:
        raw = await chat_completion(system=_rollup_system(), user=user_msg)
        obj = extract_json_object(raw)
        rolled = str(obj.get("rolling_summary") or "").strip()
    except (LlmError, ValueError) as e:
        logger.warning("滚动摘要失败，使用截断拼接: %s", e)
        rolled = (prev + "\n" + older_text).strip()[:4000]

    if rolled:
        data["rolling_summary"] = rolled
    data["messages"] = recent if recent else messages[-RECENT_KEEP:]


async def _close_session(lang: str, data: dict[str, Any], *, reason: str) -> dict[str, Any]:
    await _compress_messages(data)
    # 再滚一次：关闭时尽量把剩余 recent 也并进摘要
    messages = list(data.get("messages") or [])
    if messages:
        prev = str(data.get("rolling_summary") or "").strip()
        text = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        user_msg = (
            f"## 已有滚动摘要\n{prev or '（无）'}\n\n"
            f"## 关闭前剩余对话\n{text}\n\n请输出最终 rolling_summary JSON。"
        )
        try:
            raw = await chat_completion(system=_rollup_system(), user=user_msg)
            obj = extract_json_object(raw)
            rolled = str(obj.get("rolling_summary") or "").strip()
            if rolled:
                data["rolling_summary"] = rolled
        except (LlmError, ValueError) as e:
            logger.warning("关闭总结失败: %s", e)
            if not prev:
                data["rolling_summary"] = text[:4000]
        # 关闭后只保留摘要 + 极短 recent（空），减少全文堆积
        data["messages"] = []

    data["status"] = "closed"
    data["closed_at"] = _now()
    data["plan_ready"] = False
    data["updated_at"] = _now()
    note = f"会话已关闭并总结（{reason}）。请「新开窗口」继续；历史可从左侧恢复摘要。"
    data.setdefault("messages", [])
    # 给 UI 一条系统提示（存进归档前写一条 assistant）
    data["messages"] = [{"role": "assistant", "content": note, "at": _now(), "mode": "system"}]
    _archive_if_needed(lang, data)
    ir.write_elicitation(lang, data)
    return data


def _ensure_open(data: dict[str, Any]) -> None:
    if (data.get("status") or "") == "closed":
        raise ElicitorError("当前会话已关闭（达上限或已归档），请「新开窗口」或从历史恢复后再聊")


async def send_message(lang: str, content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ElicitorError("消息不能为空")
    if _is_useless_message(text):
        raise ElicitorError("请描述具体需求（目标、功能、接口等），无意义短句不会调用模型")

    data = get_or_create_elicitation(lang)
    _ensure_open(data)

    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if _user_turn_count(messages) >= get_max_turns():
        data = await _close_session(lang, data, reason=f"已达 {get_max_turns()} 轮")
        raise ElicitorError(f"已达最大轮数 {get_max_turns()}，会话已关闭并总结，请新开窗口")

    messages.append({"role": "user", "content": text, "at": _now(), "mode": "chat"})
    data["messages"] = messages
    data["plan_ready"] = False
    data["status"] = "drafting"
    data["updated_at"] = _now()

    if _messages_chars(messages) >= MAX_CHARS:
        await _compress_messages(data)
        messages = list(data.get("messages") or [])

    user_msg = f"{_context_block(data)}\n\n请给出下一句澄清回复（JSON）。"
    try:
        raw = await chat_completion(system=_chat_system(lang), user=user_msg)
        obj = extract_json_object(raw)
        reply = str(obj.get("reply") or "").strip()
        ready = bool(obj.get("ready_to_plan") or obj.get("ready_to_conclude"))
    except (LlmError, ValueError) as e:
        logger.warning("elicit message LLM 失败: %s", e)
        reply = "收到。请补充：核心业务对象、主要操作（增删改查）、以及必须有的接口？"
        ready = _user_turn_count(messages) >= 3

    if not reply:
        reply = "请再描述一下你希望系统完成的核心能力。"

    messages = list(data.get("messages") or [])
    messages.append({"role": "assistant", "content": reply, "at": _now(), "mode": "chat"})
    data["messages"] = messages
    data["updated_at"] = _now()

    turns = _user_turn_count(messages)
    if turns >= get_max_turns():
        data = await _close_session(lang, data, reason=f"已达 {get_max_turns()} 轮")
        return {
            "elicitation": data,
            "reply": reply + f"\n\n（已达 {get_max_turns()} 轮，会话已关闭并总结，请新开窗口）",
            "ready_to_conclude": False,
            "ready_to_plan": False,
            "user_turns": turns,
            "max_turns": get_max_turns(),
            "session_closed": True,
        }

    ir.write_elicitation(lang, data)
    return {
        "elicitation": data,
        "reply": reply,
        "ready_to_conclude": ready,
        "ready_to_plan": ready,
        "user_turns": turns,
        "max_turns": get_max_turns(),
        "session_closed": False,
    }


async def conclude(lang: str) -> dict[str, Any]:
    """兼容旧接口：仅整理结论，不写 docs、不生成代码。"""
    data = get_or_create_elicitation(lang)
    _ensure_open(data)
    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if not messages and not str(data.get("rolling_summary") or "").strip():
        raise ElicitorError("尚无对话，无法总结")

    user_msg = f"{_context_block(data)}\n\n请输出结论 JSON。"
    try:
        raw = await chat_completion(system=_conclude_system(lang), user=user_msg)
        obj = extract_json_object(raw)
    except (LlmError, ValueError) as e:
        raise ElicitorError(f"总结失败: {e}") from e

    data["conclusion"] = _parse_conclusion(obj)
    data["status"] = "drafting"
    data["plan_ready"] = False
    data["updated_at"] = _now()
    ir.write_elicitation(lang, data)
    return {"elicitation": data}


async def run_plan(
    lang: str,
    *,
    content: str | None = None,
    conclusion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """分析计划：更新结论 → analyze/docs/change_plan，不写业务代码。"""
    from backend.services.analyze import AnalyzeError, analyze_requirements

    data = get_or_create_elicitation(lang)
    _ensure_open(data)

    text = (content or "").strip()
    if text and _is_useless_message(text):
        # 分析计划时忽略无意义附言，不写入、不额外占轮次
        text = ""
    messages: list[dict[str, Any]] = list(data.get("messages") or [])
    if text:
        if _user_turn_count(messages) >= get_max_turns():
            data = await _close_session(lang, data, reason=f"已达 {get_max_turns()} 轮")
            raise ElicitorError(f"已达最大轮数 {get_max_turns()}，会话已关闭并总结，请新开窗口")
        messages.append({"role": "user", "content": text, "at": _now(), "mode": "plan"})
        data["messages"] = messages

    if not messages and not str(data.get("rolling_summary") or "").strip() and not conclusion:
        raise ElicitorError("请先聊天描述需求，再点「分析计划」")

    # 结论：优先前端编辑稿；否则从对话生成
    if conclusion and str(conclusion.get("summary") or "").strip():
        merged = _merge_conclusion(
            data.get("conclusion") if isinstance(data.get("conclusion"), dict) else {},
            conclusion,
        )
    else:
        user_msg = f"{_context_block(data)}\n\n请输出结论 JSON（用于制定变更计划）。"
        try:
            raw = await chat_completion(system=_conclude_system(lang), user=user_msg)
            obj = extract_json_object(raw)
            merged = _parse_conclusion(obj)
        except (LlmError, ValueError) as e:
            raise ElicitorError(f"分析计划：整理结论失败: {e}") from e

    data["conclusion"] = merged
    directives = _latest_user_directives(data)
    spec_text = conclusion_to_spec_text(
        merged,
        rolling_summary=str(data.get("rolling_summary") or ""),
        user_directives=directives,
    )
    try:
        analyze_result = await analyze_requirements(lang, spec_text)
    except AnalyzeError as e:
        raise ElicitorError(f"分析计划失败: {e}") from e

    plan = ir.read_change_plan(lang) or {}
    last_plan = {
        "summary": str(plan.get("summary") or merged.get("summary") or "").strip(),
        "task_count": len(plan.get("tasks") or []),
        "at": _now(),
    }
    reply = conclusion_to_chat_text(merged, task_count=int(last_plan["task_count"]))
    messages = list(data.get("messages") or [])
    messages.append({"role": "assistant", "content": reply, "at": _now(), "mode": "plan"})
    data["messages"] = messages
    data["last_plan"] = last_plan
    data["plan_ready"] = True
    data["status"] = "planned"
    data["updated_at"] = _now()

    await _compress_messages(data)
    if _user_turn_count(list(data.get("messages") or [])) >= get_max_turns():
        # 计划完成后再关：先落盘计划结果
        ir.write_elicitation(lang, data)
        data = await _close_session(lang, data, reason=f"已达 {get_max_turns()} 轮")
        return {
            "elicitation": data,
            "analyze": analyze_result,
            "plan_ready": False,
            "last_plan": last_plan,
            "session_closed": True,
        }

    ir.write_elicitation(lang, data)
    return {
        "elicitation": data,
        "analyze": analyze_result,
        "plan_ready": True,
        "last_plan": last_plan,
        "session_closed": False,
    }


async def run_execute(lang: str) -> dict[str, Any]:
    """执行生成：必须先有计划；生成/修改代码，不自动启动。"""
    from backend.services.codegen import CodegenError
    from backend.services.frontend_codegen import FRONTEND_PORT
    from backend.services.orchestrator import OrchestratorError, run_generate
    from backend.services.runtime import kill_port, smoke_after_generate

    data = get_or_create_elicitation(lang)
    _ensure_open(data)

    plan = ir.read_change_plan(lang)
    if not data.get("plan_ready") and not (plan and plan.get("approved")):
        raise ElicitorError("请先点「分析计划」再执行生成")
    if not plan:
        raise ElicitorError("尚无 change_plan，请先「分析计划」")

    # 执行前停前端，避免清空 frontend/node_modules 时 WinError 5
    try:
        kill_port(FRONTEND_PORT)
    except Exception as e:
        logger.warning("执行前停止前端端口失败（继续生成）: %s", e)

    try:
        gen = await run_generate(lang, None, use_docs=True)
    except (OrchestratorError, CodegenError) as e:
        raise ElicitorError(f"执行生成失败: {e}") from e

    smoke = smoke_after_generate(lang, plan=plan, endpoints=gen.get("endpoints") or [])
    fe_ok = gen.get("frontend_ok")
    fe_err = str(gen.get("frontend_error") or "").strip()
    reply = (
        f"代码已生成/更新。后端文件 {len(gen.get('files') or [])} 个。"
        + (
            f" 前端：{'成功' if fe_ok else '跳过/失败'}。"
            if gen.get("frontend_port") is not None or fe_ok is not None
            else ""
        )
    )
    if fe_err and not fe_ok:
        reply += f" 前端错误：{fe_err[:200]}。"
    reply += f" 冒烟：{smoke.get('message') or '未执行'}。"
    reply += " 请用「运行」页启动后端/前端；可继续聊天后再次「分析计划」做迭代。"
    messages = list(data.get("messages") or [])
    messages.append({"role": "assistant", "content": reply, "at": _now(), "mode": "execute"})
    data["messages"] = messages
    data["status"] = "planned"
    data["plan_ready"] = True  # 允许同计划再执行；新聊天会清掉
    data["updated_at"] = _now()
    await _compress_messages(data)
    ir.write_elicitation(lang, data)
    return {"elicitation": data, "generate": gen, "smoke": smoke}


async def confirm(lang: str, conclusion: dict[str, Any] | None = None) -> dict[str, Any]:
    """兼容旧接口：等同「分析计划」（不生成代码）。"""
    result = await run_plan(lang, conclusion=conclusion)
    return {"elicitation": result["elicitation"], "analyze": result["analyze"]}


async def new_session(lang: str) -> dict[str, Any]:
    current = ir.read_elicitation(lang)
    if current and (
        current.get("messages")
        or current.get("conclusion")
        or str(current.get("rolling_summary") or "").strip()
    ):
        current = _normalize_session(current, lang)
        if (current.get("status") or "") != "closed":
            try:
                await _compress_messages(current)
            except Exception as e:  # noqa: BLE001 — 切换会话不因摘要失败阻断
                logger.warning("新开会话前压缩失败: %s", e)
            current["status"] = "closed"
            current["closed_at"] = _now()
            current["updated_at"] = _now()
        _archive_if_needed(lang, current)
    data = _new_session(lang)
    ir.write_elicitation(lang, data)
    return {"elicitation": data}


def restore_session(lang: str, session_id: str) -> dict[str, Any]:
    snap = ir.read_session(lang, session_id)
    if not snap:
        raise ElicitorError(f"会话不存在: {session_id}")
    current = ir.read_elicitation(lang)
    if current and (
        current.get("messages")
        or current.get("conclusion")
        or str(current.get("rolling_summary") or "").strip()
    ):
        if current.get("session_id") != snap.get("session_id"):
            cur = _normalize_session(dict(current), lang)
            if (cur.get("status") or "") != "closed":
                cur["status"] = "closed"
                cur["closed_at"] = _now()
                cur["updated_at"] = _now()
            _archive_if_needed(lang, cur)
    restored = _normalize_session(dict(snap), lang)
    restored["lang"] = lang
    restored["updated_at"] = _now()
    # 恢复后允许继续：closed/confirmed → drafting/planned
    if restored.get("status") == "closed":
        restored["status"] = "planned" if restored.get("plan_ready") or restored.get("conclusion") else "drafting"
        restored["closed_at"] = None
        # 恢复时以摘要为主；若无 recent 原文，放一条提示
        if not restored.get("messages"):
            summary = str(restored.get("rolling_summary") or "").strip()
            tip = "已从历史恢复。" + (f" 摘要：{summary[:500]}" if summary else " 可继续补充需求后「分析计划」。")
            restored["messages"] = [{"role": "assistant", "content": tip, "at": _now(), "mode": "system"}]
    ir.write_elicitation(lang, restored)
    return {"elicitation": restored}


def list_history(lang: str) -> dict[str, Any]:
    return {"lang": lang, "sessions": ir.list_sessions(lang)}


async def close_current_session(lang: str) -> dict[str, Any]:
    data = get_or_create_elicitation(lang)
    if (data.get("status") or "") == "closed":
        return {"elicitation": data}
    data = await _close_session(lang, data, reason="用户手动关闭")
    return {"elicitation": data}


def delete_history_session(lang: str, session_id: str) -> dict[str, Any]:
    ok = ir.delete_session(lang, session_id)
    if not ok:
        raise ElicitorError(f"会话不存在: {session_id}")
    return {"lang": lang, "session_id": session_id, "deleted": True}
