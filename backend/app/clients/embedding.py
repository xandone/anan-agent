"""Embedding 客户端：BGE-M3，OpenAI 兼容端点。"""
from openai import OpenAI

from app.core.config import get_settings


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.embedding_api_url, api_key=s.embedding_api_key)


def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    resp = _client().embeddings.create(model=s.embedding_model, input=texts)
    return [item.embedding for item in resp.data]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
