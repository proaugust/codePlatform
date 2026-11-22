from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

# lang -> subscriber queues（进程内；无订阅者时 publish 静默）
_subscribers: dict[str, list[asyncio.Queue[dict[str, Any] | None]]] = defaultdict(list)


def subscribe(lang: str) -> asyncio.Queue[dict[str, Any] | None]:
    lang = lang.lower().strip()
    q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=64)
    _subscribers[lang].append(q)
    return q


def unsubscribe(lang: str, q: asyncio.Queue[dict[str, Any] | None]) -> None:
    lang = lang.lower().strip()
    subs = _subscribers.get(lang) or []
    if q in subs:
        subs.remove(q)
    if not subs and lang in _subscribers:
        del _subscribers[lang]


def publish(lang: str, payload: dict[str, Any]) -> None:
    lang = lang.lower().strip()
    for q in list(_subscribers.get(lang) or []):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
