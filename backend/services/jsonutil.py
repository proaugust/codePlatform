from __future__ import annotations

import json
import re
from typing import Any

_SMART_QUOTES = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\ufeff": "",
    }
)


def _normalize_json_text(text: str) -> str:
    t = text.strip().translate(_SMART_QUOTES)
    # 去掉常见尾部残缺：未闭合字符串后的垃圾
    return t


def _escape_controls_in_strings(text: str) -> str:
    """修复 LLM 常见问题：JSON 字符串值内出现未转义的换行/制表符。"""
    out: list[str] = []
    in_str = False
    escape = False
    for ch in text:
        if escape:
            out.append(ch)
            escape = False
            continue
        if in_str and ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            continue
        if in_str and ch in "\n\r\t":
            out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
            continue
        out.append(ch)
    return "".join(out)


def _loads_dict(candidate: str) -> dict[str, Any] | None:
    for variant in (candidate, _escape_controls_in_strings(candidate)):
        try:
            data = json.loads(variant)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _try_trim_trailing(candidate: str) -> dict[str, Any] | None:
    """从末尾逐步缩短，尝试找到可解析的最大前缀对象。"""
    end = candidate.rfind("}")
    while end > 0:
        data = _loads_dict(candidate[: end + 1])
        if data is not None:
            return data
        end = candidate.rfind("}", 0, end)
    return None


def extract_json_object(text: str) -> dict[str, Any]:
    text = _normalize_json_text(text or "")
    if not text:
        raise ValueError("无法解析 LLM 返回的 JSON：空内容")

    data = _loads_dict(text)
    if data is not None:
        return data

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        chunk = _normalize_json_text(fence.group(1))
        data = _loads_dict(chunk)
        if data is not None:
            return data
        data = _try_trim_trailing(chunk)
        if data is not None:
            return data

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        chunk = text[start : end + 1]
        data = _loads_dict(chunk)
        if data is not None:
            return data
        data = _try_trim_trailing(chunk)
        if data is not None:
            return data

    raise ValueError("无法解析 LLM 返回的 JSON（可能被截断或含非法转义）")
