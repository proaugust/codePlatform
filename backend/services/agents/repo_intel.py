from __future__ import annotations

import logging
from typing import Any

from backend.core.config import LANG_PORTS
from backend.services import ir
from backend.services.structure import scan_project, write_structure_doc

logger = logging.getLogger(__name__)

JAVA_BASELINE = {
    "stack": "Spring Boot 3.x / Maven / Java 17+",
    "package_root": "com.example.autocode",
    "layers": ["controller", "service", "repository"],
    "conventions": [
        "REST Controller-Service-Repository",
        "Prefer H2 in-memory unless docs require otherwise",
        "Always expose GET /health returning JSON {status:ok}",
        "Enable CORS for Vite 5173/5174",
    ],
}

GO_BASELINE = {
    "stack": "Go standard library net/http only",
    "module": "example.com/autocode",
    "layers": ["handler", "service", "repository"],
    "conventions": [
        "No third-party web frameworks",
        "Always expose GET /health returning JSON {status:ok}",
        "Enable CORS for Vite 5173/5174",
    ],
}


def _baseline(lang: str) -> dict[str, Any]:
    port = LANG_PORTS[lang]
    base = dict(JAVA_BASELINE if lang == "java" else GO_BASELINE)
    base["port"] = port
    base["mode"] = "greenfield"
    return base


async def run_repo_intel(lang: str) -> dict[str, Any]:
    """扫描目标仓（从零多为空）并写入 05-structure.md + codebase_ir.json。"""
    structure_file = write_structure_doc(lang)
    scan = scan_project(lang)
    payload = {
        "lang": lang,
        "mode": "greenfield",
        "baseline": _baseline(lang),
        "scan": scan.to_dict(),
    }
    path = ir.write_codebase_ir(lang, payload)
    logger.info("RepoIntel 完成 lang=%s ir=%s has_code=%s", lang, path, scan.has_code)
    return {
        "structure_file": structure_file,
        "codebase_ir": payload,
        "ir_path": str(path),
    }
