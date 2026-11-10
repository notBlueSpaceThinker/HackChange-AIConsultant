from functools import lru_cache

from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient, models

from src.config import settings

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


@lru_cache
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant.url)


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.qdrant.url)


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


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        collection_name=settings.qdrant.collection_name,
        client=get_qdrant_client(),
        aclient=get_async_qdrant_client(),
        enable_hybrid=True,
        fastembed_sparse_model="Qdrant/bm25",
        dense_vector_name=DENSE_VECTOR_NAME,
        sparse_vector_name=SPARSE_VECTOR_NAME,
    )


def clear_cache() -> None:
    get_async_qdrant_client.cache_clear()
    get_qdrant_client.cache_clear()
    get_vector_store.cache_clear()


async def close_qdrant_client() -> None:
    await get_async_qdrant_client().close()
    get_qdrant_client().close()
    clear_cache()
