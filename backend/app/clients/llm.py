"""LLM 客户端：OpenAI 兼容端点，配置可运行时动态更新。"""
import json

from openai import OpenAI

from app.core.config import get_settings


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.llm_api_url, api_key=s.llm_api_key)


def chat(messages: list[dict], temperature: float = 0.7, **kwargs) -> str:
    s = get_settings()
    resp = _client().chat.completions.create(
        model=s.llm_model,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    return resp.choices[0].message.content


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict:
    """要求模型输出 JSON 并解析，失败时抛异常由调用方重试。"""
    content = chat(messages, temperature=temperature,
                   response_format={"type": "json_object"})
    return json.loads(content)


def chat_stream(messages: list[dict], temperature: float = 0.7):
    """流式对话。逐块产出 ("delta", 文本)，最后产出 ("usage", dict|None)。"""
    s = get_settings()
    stream = _client().chat.completions.create(
        model=s.llm_model,
        messages=messages,
        temperature=temperature,
        stream=True,
        stream_options={"include_usage": True},  # 端点不支持时 usage 为空，不影响流
    )
    usage = None
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
        if chunk.choices and chunk.choices[0].delta.content:
            yield ("delta", chunk.choices[0].delta.content)
    yield ("usage", usage)
