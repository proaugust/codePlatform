from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.config import settings

PREFS_NAME = ".platform_prefs.json"
DEFAULT_MAX_TURNS = 20
MIN_MAX_TURNS = 3
MAX_MAX_TURNS = 50
DEFAULT_TREE_INDENT_CH = 2
MIN_TREE_INDENT_CH = 1
MAX_TREE_INDENT_CH = 8

_LLM_STR_KEYS = ("llm_base_url", "llm_api_key", "llm_model")


def _prefs_path() -> Path:
    root = settings.auto_code_root
    root.mkdir(parents=True, exist_ok=True)
    return root / PREFS_NAME


def _clamp_max_turns(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_TURNS
    return max(MIN_MAX_TURNS, min(MAX_MAX_TURNS, n))


def _clamp_tree_indent_ch(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_TREE_INDENT_CH
    return max(MIN_TREE_INDENT_CH, min(MAX_TREE_INDENT_CH, n))


def _normalize_llm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def read_prefs() -> dict[str, Any]:
    path = _prefs_path()
    data: dict[str, Any] = {
        "max_turns": DEFAULT_MAX_TURNS,
        "tree_indent_ch": DEFAULT_TREE_INDENT_CH,
        "llm_base_url": "",
        "llm_api_key": "",
        "llm_model": "",
    }
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    data["max_turns"] = _clamp_max_turns(data.get("max_turns", DEFAULT_MAX_TURNS))
    data["tree_indent_ch"] = _clamp_tree_indent_ch(data.get("tree_indent_ch", DEFAULT_TREE_INDENT_CH))
    for key in _LLM_STR_KEYS:
        data[key] = _normalize_llm_str(data.get(key, ""))
    return data


def write_prefs(patch: dict[str, Any]) -> dict[str, Any]:
    current = read_prefs()
    if "max_turns" in patch and patch["max_turns"] is not None:
        current["max_turns"] = _clamp_max_turns(patch["max_turns"])
    if "tree_indent_ch" in patch and patch["tree_indent_ch"] is not None:
        current["tree_indent_ch"] = _clamp_tree_indent_ch(patch["tree_indent_ch"])
    # llm_api_key: None/missing = keep; "" = clear; non-empty = set
    if "llm_api_key" in patch and patch["llm_api_key"] is not None:
        current["llm_api_key"] = _normalize_llm_str(patch["llm_api_key"])
    for key in ("llm_base_url", "llm_model"):
        if key in patch and patch[key] is not None:
            current[key] = _normalize_llm_str(patch[key])
    path = _prefs_path()
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return current


def get_max_turns() -> int:
    return int(read_prefs()["max_turns"])


def get_tree_indent_ch() -> int:
    return int(read_prefs()["tree_indent_ch"])


def mask_api_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return "****"
    return f"{k[:3]}****{k[-4:]}"


def resolve_llm_config() -> dict[str, str]:
    """Prefs 非空优先，否则回退 settings（.env）。"""
    prefs = read_prefs()
    base_url = prefs.get("llm_base_url") or settings.llm_base_url
    api_key = prefs.get("llm_api_key") or settings.llm_api_key
    model = prefs.get("llm_model") or settings.llm_model
    return {
        "llm_base_url": str(base_url).strip(),
        "llm_api_key": str(api_key).strip(),
        "llm_model": str(model).strip(),
    }
