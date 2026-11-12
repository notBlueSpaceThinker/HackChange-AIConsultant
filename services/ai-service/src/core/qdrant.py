from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

from src.config import settings

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_MODEL_NAME = "Qdrant/bm25"


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(location=settings.qdrant.url)


async def create_collection_if_not_exists(
    collection_name: str = settings.qdrant.collection_name,
    vector_dimension: int = settings.embedding.embed_dim,
) -> None:
    client = get_async_qdrant_client()
    if not await client.collection_exists(collection_name):
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=vector_dimension,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    index=models.SparseIndexParams(),
                    modifier=models.Modifier.IDF,
                ),
            },
        )


def clear_cache() -> None:
    get_async_qdrant_client.cache_clear()


async def close_qdrant_client() -> None:
    if get_async_qdrant_client.cache_info().currsize:
        await get_async_qdrant_client().close()
    clear_cache()
