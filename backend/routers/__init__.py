from __future__ import annotations

from fastapi import APIRouter

from backend.routers import agent, demo


def all_routers() -> list[APIRouter]:
    # 前端只调 Py Agent 接口；java/go 仅是生成产物 target
    return [demo.router, agent.router]
