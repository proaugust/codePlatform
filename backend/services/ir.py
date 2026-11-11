from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.config import settings

IR_DIR_NAME = "ir"
RUN_FILE = "run.json"
SPEC_FILE = "spec.json"
CODEBASE_IR_FILE = "codebase_ir.json"
CHANGE_PLAN_FILE = "change_plan.json"
VALIDATION_FILE = "validation.json"

RUN_STATES = frozenset(
    {
        "INIT",
        "REQUIRE",
        "INTEL",
        "PLAN",
        "AWAITING_APPROVAL",
        "CODE",
        "VALIDATE",
        "REVIEW",
        "DONE",
        "FAILED",
    }
)


def docs_dir(lang: str) -> Path:
    return settings.auto_code_dir(lang) / "docs"


def ir_dir(lang: str) -> Path:
    return docs_dir(lang) / IR_DIR_NAME


def ensure_ir_dir(lang: str) -> Path:
    path = ir_dir(lang)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(lang: str, filename: str, data: dict[str, Any]) -> Path:
    out = ensure_ir_dir(lang) / filename
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return out


def read_json(lang: str, filename: str) -> dict[str, Any] | None:
    path = ir_dir(lang) / filename
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_run(lang: str, data: dict[str, Any]) -> Path:
    return write_json(lang, RUN_FILE, data)


def read_run(lang: str) -> dict[str, Any] | None:
    return read_json(lang, RUN_FILE)


def write_spec(lang: str, data: dict[str, Any]) -> Path:
    return write_json(lang, SPEC_FILE, data)


def read_spec(lang: str) -> dict[str, Any] | None:
    return read_json(lang, SPEC_FILE)


def write_codebase_ir(lang: str, data: dict[str, Any]) -> Path:
    return write_json(lang, CODEBASE_IR_FILE, data)


def read_codebase_ir(lang: str) -> dict[str, Any] | None:
    return read_json(lang, CODEBASE_IR_FILE)


def write_change_plan(lang: str, data: dict[str, Any]) -> Path:
    return write_json(lang, CHANGE_PLAN_FILE, data)


def read_change_plan(lang: str) -> dict[str, Any] | None:
    return read_json(lang, CHANGE_PLAN_FILE)


def write_validation(lang: str, data: dict[str, Any]) -> Path:
    return write_json(lang, VALIDATION_FILE, data)


def read_validation(lang: str) -> dict[str, Any] | None:
    return read_json(lang, VALIDATION_FILE)
