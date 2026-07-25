from dotenv import load_dotenv

load_dotenv()

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    api_prefix: str = "/api/v1"
    admin_token: str = ""
    model_dir: Path | None = None
    model_local_only: bool = False
    inline_worker: bool = True
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-pro"
    llm_timeout_seconds: float = 120.0


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    configured = os.getenv("EMBODIED_DB_PATH")
    database_path = Path(configured).resolve() if configured else project_root / "data" / "embodied_ai_jobs_v4.db"
    model_dir_value = os.getenv("EMBODIED_MODEL_DIR")
    return Settings(
        database_path=database_path,
        admin_token=os.getenv("EMBODIED_ADMIN_TOKEN", ""),
        model_dir=Path(model_dir_value).resolve() if model_dir_value else project_root / "models",
        model_local_only=os.getenv("EMBODIED_MODEL_LOCAL_ONLY", "0") == "1",
        inline_worker=os.getenv("EMBODIED_INLINE_WORKER", "1") == "1",
        llm_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        llm_base_url=os.getenv("EMBODIED_LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        llm_model=os.getenv("EMBODIED_LLM_MODEL", "deepseek-v4-pro"),
        llm_timeout_seconds=float(os.getenv("EMBODIED_LLM_TIMEOUT_SECONDS", "120")),
    )
