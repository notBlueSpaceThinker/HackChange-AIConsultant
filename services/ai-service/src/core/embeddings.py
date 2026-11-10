from functools import lru_cache

from llama_index.core import Settings
from llama_index.core.base.embeddings.base import BaseEmbedding, Embedding
from llama_index.core.embeddings import MockEmbedding
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

from src.config import settings


@lru_cache
def get_embedding_model() -> BaseEmbedding:
    if settings.is_embedding_mock:
        embed_model: BaseEmbedding = MockEmbedding(embed_dim=settings.embedding.embed_dim)
    else:
        embed_model = OpenAILikeEmbedding(
            api_base=settings.embedding.url,
            api_key=settings.embedding.api_key,
            model_name=str(settings.embedding.model),
            timeout=settings.embedding.timeout,
            max_retries=settings.embedding.max_retries,
        )
    Settings.embed_model = embed_model
    return embed_model


async def embed_query(query: str) -> Embedding:
    model = get_embedding_model()
    return await model.aget_query_embedding(query)


async def embed_texts(texts: list[str]) -> list[Embedding]:
    model = get_embedding_model()
    return await model.aget_text_embedding_batch(texts)
