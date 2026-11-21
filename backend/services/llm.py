from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from backend.core.config import settings
from backend.services.jsonutil import extract_json_object
from backend.services.platform_prefs import resolve_llm_config

logger = logging.getLogger(__name__)

# 复用连接，避免每次 TCP+TLS；timeout 取当前 settings
_client: httpx.AsyncClient | None = None


class LlmError(RuntimeError):
    pass


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.llm_timeout)
    return _client


async def chat_completion(*, system: str, user: str) -> str:
    llm = resolve_llm_config()
    api_key = llm["llm_api_key"]
    if not api_key:
        raise LlmError("未配置 LLM API Key，请在设置页或 .env 中填写")

    model = llm["llm_model"]
    url = llm["llm_base_url"].rstrip("/") + "/v1/chat/completions"
    # DeepSeek Flash/Pro 默认开启 thinking（effort=high），结构化 JSON 场景会明显变慢
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    t0 = time.perf_counter()
    try:
        resp = await _get_client().post(url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise LlmError(f"调用 LLM 失败: {e}") from e

    elapsed_ms = (time.perf_counter() - t0) * 1000
    if resp.status_code >= 400:
        logger.warning("LLM HTTP %s model=%s ms=%.0f body=%s", resp.status_code, model, elapsed_ms, resp.text[:400])
        raise LlmError(f"LLM HTTP {resp.status_code}: {resp.text[:800]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LlmError(f"LLM 返回格式异常: {data!r}") from e

    if not isinstance(content, str) or not content.strip():
        raise LlmError("LLM 返回空内容")
    logger.info(
        "LLM ok model=%s ms=%.0f in=%d out=%d",
        model,
        elapsed_ms,
        len(system) + len(user),
        len(content),
    )
    return content


async def chat_completion_json(
    *,
    system: str,
    user: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """调用 LLM 并解析为 JSON 对象；解析失败同 prompt 重试。"""
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw = await chat_completion(system=system, user=user)
            try:
                return extract_json_object(raw)
            except ValueError as e:
                last_err = e
                preview = f"{raw[:500]}…{raw[-500:]}" if len(raw) > 1000 else raw
                logger.warning(
                    "LLM JSON 解析失败 attempt=%d/%d err=%s preview=%s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                    preview[:800],
                )
        except LlmError as e:
            last_err = e
            logger.warning(
                "LLM 调用失败 attempt=%d/%d err=%s",
                attempt + 1,
                max_retries + 1,
                e,
            )
    raise LlmError(
        f"JSON 解析失败，未写入任何文件（已重试 {max_retries} 次）: {last_err}"
    ) from last_err
