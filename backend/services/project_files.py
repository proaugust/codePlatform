from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services.codegen import SUPPORTED_LANGS

SKIP_DIR_NAMES = frozenset(
    {
        "node_modules",
        "target",
        "dist",
        "build",
        ".git",
        ".idea",
        ".vscode",
        "__pycache__",
        ".vite",
        ".vite-temp",
        "coverage",
        "vendor",
    }
)
MAX_FILE_BYTES = 512 * 1024
TEXT_SUFFIXES = frozenset(
    {
        ".java",
        ".go",
        ".kt",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".vue",
        ".json",
        ".md",
        ".txt",
        ".xml",
        ".yml",
        ".yaml",
        ".toml",
        ".properties",
        ".gradle",
        ".sql",
        ".html",
        ".css",
        ".scss",
        ".bat",
        ".sh",
        ".env",
        ".gitignore",
        ".dockerignore",
        ".mod",
        ".sum",
    }
)
TEXT_NAMES = frozenset({"Dockerfile", "Makefile", "Procfile", "LICENSE", "README"})


class ProjectFilesError(RuntimeError):
    pass


def _root(lang: str) -> Path:
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGS:
        raise ProjectFilesError(f"不支持的语言: {lang}")
    root = settings.auto_code_dir(lang)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve_under_root(lang: str, rel_path: str) -> Path:
    root = _root(lang)
    raw = (rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not raw or raw == ".":
        return root
    if ".." in Path(raw).parts:
        raise ProjectFilesError("非法路径")
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ProjectFilesError("路径越界") from e
    return candidate


def _is_probably_text(path: Path) -> bool:
    if path.name in TEXT_NAMES:
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    # 无后缀小文件尝试当文本
    return path.suffix == "" and path.stat().st_size <= 64 * 1024


def _build_tree(dir_path: Path, root: Path) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return nodes
    for entry in entries:
        if entry.name in SKIP_DIR_NAMES:
            continue
        if entry.name.startswith(".") and entry.name not in {".gitignore", ".env", ".dockerignore"}:
            # 仍跳过多数隐藏目录；允许个别配置文件
            if entry.is_dir():
                continue
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            nodes.append(
                {
                    "name": entry.name,
                    "path": rel,
                    "type": "dir",
                    "children": _build_tree(entry, root),
                }
            )
        elif entry.is_file():
            nodes.append({"name": entry.name, "path": rel, "type": "file", "children": None})
    return nodes


def list_tree(lang: str) -> dict[str, Any]:
    root = _root(lang)
    return {
        "lang": lang.lower().strip(),
        "root": str(root),
        "tree": _build_tree(root, root) if root.is_dir() else [],
    }


def read_file(lang: str, rel_path: str) -> dict[str, Any]:
    path = resolve_under_root(lang, rel_path)
    if not path.is_file():
        raise ProjectFilesError(f"文件不存在: {rel_path}")
    if not _is_probably_text(path):
        raise ProjectFilesError("暂不支持预览该二进制/未知类型文件")
    size = path.stat().st_size
    truncated = size > MAX_FILE_BYTES
    raw = path.read_bytes()[:MAX_FILE_BYTES]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return {
        "lang": lang.lower().strip(),
        "path": path.relative_to(_root(lang)).as_posix(),
        "content": text,
        "size": size,
        "truncated": truncated,
    }
