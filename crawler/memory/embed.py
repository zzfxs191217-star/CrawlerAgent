"""向量化：通过百炼 OpenAI 兼容 Embeddings 接口生成文本向量。"""

from __future__ import annotations

from openai import OpenAI

from .. import config

EMBED_MODEL = "text-embedding-v3"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.LLM_BASE_URL or not config.DASHSCOPE_API_KEY:
            raise SystemExit("请先配置 .env（参考 .env.example）")
        _client = OpenAI(api_key=config.DASHSCOPE_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    client = _get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend(item.embedding for item in resp.data)
    return vectors