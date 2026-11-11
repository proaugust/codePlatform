from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        data = json.loads(fence.group(1).strip())
        if isinstance(data, dict):
            return data

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data

    raise ValueError("无法解析 LLM 返回的 JSON")
