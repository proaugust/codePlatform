from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEFAULT_AUTO_CODE_LANGS = ("java", "go")
LANG_PORTS: dict[str, int] = {"java": 8070, "go": 8072}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8-sig",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "Code Platform"
    debug: bool = False
    # Docker/生产设为 true：API 挂 /api 前缀并托管 static/；本地不设，保持 Vite 代理
    serve_static: bool = False
    # 生成代码根目录（默认项目内 auto_code），实际路径 = {auto_code_root}/{lang}
    auto_code_root: Path = BASE_DIR / "auto_code"
    # 控制台 / 未显式指定 target 时的默认语言（可用 DEFAULT_LANG 覆盖）
    default_lang: str = Field(default="java", validation_alias=AliasChoices("DEFAULT_LANG", "default_lang"))

    # DeepSeek（OpenAI 兼容）；Key 优先 LLM_API_KEY，空则回退 OPENAI_API_KEY
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 180.0

    # 5+1 编排：Planner 后是否自动批准（true 兼容现前端两步流）
    auto_approve_plan: bool = True
    # Validator 失败后回喂 Coder 的最大次数
    validate_max_repairs: int = 3

    @field_validator("default_lang")
    @classmethod
    def _normalize_default_lang(cls, v: str) -> str:
        t = (v or "java").lower().strip()
        if t not in LANG_PORTS:
            raise ValueError("default_lang 仅支持 java | go")
        return t

    def auto_code_dir(self, lang: str) -> Path:
        return self.auto_code_root / lang.lower()

    def ensure_auto_code_dirs(self, langs: tuple[str, ...] = DEFAULT_AUTO_CODE_LANGS) -> list[Path]:
        created: list[Path] = []
        for lang in langs:
            path = self.auto_code_dir(lang)
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        return created


settings = Settings()
