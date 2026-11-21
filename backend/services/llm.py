from __future__ import annotations

import logging
import time

import httpx

from backend.core.config import settings
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
