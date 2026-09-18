"""配置路由：查看/动态更新 LLM、Embedding 等配置。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings, reload_settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def show_config():
    s = get_settings()
    return {
        "llm_api_url": s.llm_api_url,
        "llm_model": s.llm_model,
        "llm_api_key": _mask(s.llm_api_key),
        "llm_thinking": s.llm_thinking,
        "embedding_api_url": s.embedding_api_url,
        "embedding_model": s.embedding_model,
        "embedding_dim": s.embedding_dim,
        "embedding_api_key": _mask(s.embedding_api_key),
        "ocr_api_url": s.ocr_api_url,
        "douyin_api_url": s.douyin_api_url,
        "whisper_model_size": s.whisper_model_size,
        "top_comments": s.top_comments,
    }


def _mask(key: str) -> str:
    return f"{key[:6]}...{key[-4:]}" if len(key) > 12 else "***"


class ConfigUpdateReq(BaseModel):
    llm_api_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_thinking: bool | None = None
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    ocr_api_url: str | None = None
    douyin_api_url: str | None = None
    top_comments: int | None = None


@router.put("")
def update_config(req: ConfigUpdateReq):
    """更新 .env 并重载配置（仅更新提供的字段）。"""
    from pathlib import Path
    env_path = Path(get_settings().model_config["env_file"])
    updates = {k.upper(): v for k, v in req.model_dump().items() if v is not None}

    lines = env_path.read_text(encoding="utf-8").splitlines()
    written = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates:
            out.append(f"{key}={updates.pop(key)}")
            written.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        out.append(f"{k}={v}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    reload_settings()
    return {"ok": True, "updated": list(written | set(updates))}
