from __future__ import annotations

import logging

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import BASE_DIR, settings
from backend.routers import all_routers

STATIC_DIR = BASE_DIR / "static"
SERVE_STATIC = settings.serve_static and STATIC_DIR.is_dir()
API_ROUTERS = all_routers()  # 仅 /agent/* ：前端调 Py Agent，java/go 为生成 target

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


def _configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    if not logging.root.handlers:
        logging.basicConfig(level=level, format="%(levelname)s:     %(name)s - %(message)s")
    else:
        logging.root.setLevel(level)
    logging.getLogger("backend").setLevel(level)


_configure_logging()
logger = logging.getLogger(__name__)

_auto_code_dirs = settings.ensure_auto_code_dirs()
logger.info("生成代码目录: %s", ", ".join(str(p) for p in _auto_code_dirs))
if not settings.llm_api_key.strip():
    logger.warning("未配置 LLM_API_KEY / OPENAI_API_KEY，/generate 将无法调用 LLM")


def _register_api_routes(app: FastAPI, *, prefix: str = "") -> None:
    if prefix:
        api_router = APIRouter(prefix=prefix)
        for router in API_ROUTERS:
            api_router.include_router(router)
        app.include_router(api_router)
    else:
        for router in API_ROUTERS:
            app.include_router(router)


app = FastAPI(title=settings.app_name, debug=settings.debug)

if SERVE_STATIC:
    logger.info("生产布局: API 前缀 /api，托管 %s", STATIC_DIR)
    _register_api_routes(app, prefix="/api")
else:
    if settings.serve_static and not STATIC_DIR.is_dir():
        logger.warning("SERVE_STATIC=1 但无 static/ 目录，已回退为本地开发路由（无 /api 前缀）")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_api_routes(app)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Hello, FastAPI!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if SERVE_STATIC:
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
        reload_includes=[".env"],
    )
