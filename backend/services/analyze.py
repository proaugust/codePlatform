from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services.structure import write_structure_doc  # noqa: F401 — 兼容旧导入

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = frozenset({"java", "go"})

# 需求分析四件套（落盘相对 docs/）；结构文档单独扫描写入
DOC_KEYS: tuple[tuple[str, str, str], ...] = (
    ("requirements", "01-requirements.md", "总需求"),
    ("architecture", "02-architecture.md", "架构"),
    ("database", "03-database.md", "数据库表"),
    ("api", "04-api.md", "接口"),
)
STRUCTURE_DOC: tuple[str, str, str] = ("structure", "05-structure.md", "工程结构")
REVIEW_DOC: tuple[str, str, str] = ("review", "06-review.md", "变更报告")


class AnalyzeError(RuntimeError):
    pass


def docs_dir(lang: str) -> Path:
    return settings.auto_code_dir(lang) / "docs"


async def analyze_requirements(lang: str, spec: str) -> dict[str, Any]:
    """编排：RepoIntel → Requirements → Planner（见 orchestrator）。"""
    from backend.services.orchestrator import OrchestratorError, run_analyze

    try:
        return await run_analyze(lang, spec)
    except OrchestratorError as e:
        raise AnalyzeError(str(e)) from e


def read_docs(lang: str) -> dict[str, Any]:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise AnalyzeError(f"不支持的语言: {lang}")
    out = docs_dir(lang)
    files: list[dict[str, str]] = []
    sk, sf, st = STRUCTURE_DOC
    sp = out / sf
    if sp.is_file():
        files.append(
            {
                "key": sk,
                "title": st,
                "path": f"docs/{sf}",
                "content": sp.read_text(encoding="utf-8"),
            }
        )
    req_count = 0
    for key, filename, title in DOC_KEYS:
        path = out / filename
        if path.is_file():
            req_count += 1
            files.append(
                {
                    "key": key,
                    "title": title,
                    "path": f"docs/{filename}",
                    "content": path.read_text(encoding="utf-8"),
                }
            )
    rk, rf, rt = REVIEW_DOC
    rp = out / rf
    if rp.is_file():
        files.append(
            {
                "key": rk,
                "title": rt,
                "path": f"docs/{rf}",
                "content": rp.read_text(encoding="utf-8"),
            }
        )
    return {
        "lang": lang,
        "docs_root": str(out),
        "exists": req_count == len(DOC_KEYS),
        "files": files,
    }


def load_docs_as_spec(lang: str) -> str:
    info = read_docs(lang)
    # 生成代码时跳过变更报告，避免干扰
    usable = [f for f in info["files"] if f.get("key") != "review"]
    if not usable:
        raise AnalyzeError(f"尚未生成需求文档，请先调用分析: auto_code/{lang}/docs")
    parts: list[str] = []
    for item in usable:
        parts.append(f"# {item['title']}\n\n{item['content'].strip()}\n")
    return "\n---\n\n".join(parts)
