from __future__ import annotations

import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)


class LlmError(RuntimeError):
    pass


async def chat_completion(*, system: str, user: str) -> str:
    if not settings.llm_api_key.strip():
        raise LlmError("未配置 LLM_API_KEY / OPENAI_API_KEY，请在 .env 或环境变量中填写")

    url = settings.llm_base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise LlmError(f"调用 LLM 失败: {e}") from e

    if resp.status_code >= 400:
        raise LlmError(f"LLM HTTP {resp.status_code}: {resp.text[:800]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LlmError(f"LLM 返回格式异常: {data!r}") from e

    if not isinstance(content, str) or not content.strip():
        raise LlmError("LLM 返回空内容")
    return content
