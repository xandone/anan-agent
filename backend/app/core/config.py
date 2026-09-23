"""应用配置：从 .env 读取，支持运行时动态覆盖（见 api/config 路由）。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # LLM
    llm_api_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_thinking: bool = False  # DeepSeek V4 思考模式（开启后先输出思考链，首字变慢）

    # Embedding
    embedding_api_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024

    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/anan_agent"

    # External services
    ocr_api_url: str = "http://localhost:9005/ocr"
    douyin_api_url: str = "http://localhost:5555"

    # ASR
    whisper_model_size: str = "medium"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # Pipeline
    data_dir: str = "./data"
    top_comments: int = 20
    classify_confidence_threshold: float = 0.7
    retrieval_max_distance: float = 0.45  # RAG 检索余弦距离上限，超过视为无关语料不注入

    # Auth
    secret_key: str = "anan-agent-dev-secret-please-change"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """修改配置后调用，清除缓存重新加载。"""
    get_settings.cache_clear()
    return get_settings()
