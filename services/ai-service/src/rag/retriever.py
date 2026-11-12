from qdrant_client import models

from src.config import settings
from src.core.embeddings import embed_query
from src.core.qdrant import (
    DENSE_VECTOR_NAME,
    SPARSE_MODEL_NAME,
    SPARSE_VECTOR_NAME,
    get_async_qdrant_client,
)
from src.core.reranker import rerank_documents
from src.schemas.domain.chunk import Chunk, ScoredChunk, SectionType

DEFAULT_EXPAND_TYPES: set[SectionType] = {
    SectionType.RESTRICTION,
    SectionType.REQUIREMENTS,
}


async def _rerank_chunks(query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
    if not chunks:
        return []
    texts = [item.chunk.content for item in chunks]
    rerank_scores = await rerank_documents(
        query=query,
        documents=texts,
        top_n=min(len(chunks), settings.reranker.top_n),
    )
    reranked = []
    for idx, score in rerank_scores:
        chunk = chunks[idx]
        chunk.score = score
        reranked.append(chunk)
    return reranked


async def _expand_chunks(
    chunks: list[ScoredChunk],
    expand_types: set[SectionType] = DEFAULT_EXPAND_TYPES,
    limit_per_doc: int = settings.rag.expand_limit_per_doc,
    top_docs: int = settings.rag.expand_top_docs,
) -> list[ScoredChunk]:
    client = get_async_qdrant_client()

    current_ids = {str(chunk.chunk.chunk_id) for chunk in chunks}
    expanded_ids = set()
    expanded_chunks = []

    doc_texts: dict[str, str] = {}
    for chunk in chunks[:top_docs]:
        if chunk.chunk.doc_id and str(chunk.chunk.doc_id) not in doc_texts:
            doc_texts[str(chunk.chunk.doc_id)] = chunk.chunk.content

    for doc_id, text in doc_texts.items():
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id),
                ),
                models.FieldCondition(
                    key="metadata.section_type",
                    match=models.MatchAny(any=[section.value for section in expand_types]),
                ),
            ],
            must_not=[models.HasIdCondition(has_id=list(current_ids | expanded_ids))],
        )
        search_result = await client.query_points(
            collection_name=settings.qdrant.collection_name,
            query=models.Document(text=text, model=SPARSE_MODEL_NAME),
            using=SPARSE_VECTOR_NAME,
            limit=limit_per_doc,
            query_filter=query_filter,
        )
        for point in search_result.points:
            expanded_ids.add(str(point.id))
            expanded_chunks.append(
                ScoredChunk(
                    chunk=Chunk.from_payload(point.payload or {}),
                    score=0.0,
                )
            )
    return expanded_chunks


# TODO: Добавить нормализацию из будущих файлов kb для query
async def retrieve(
    query: str,
    top_k: int = settings.rag.top_k,
    with_rerank: bool = True,
    reranker_threshold: float = settings.rag.reranker_threshold,
    with_expansion: bool = True,
) -> list[ScoredChunk]:
    client = get_async_qdrant_client()
    search_result = await client.query_points(
        collection_name=settings.qdrant.collection_name,
        prefetch=[
            models.Prefetch(
                query=await embed_query(query),
                using=DENSE_VECTOR_NAME,
                limit=top_k,
            ),
            models.Prefetch(
                query=models.Document(text=query, model=SPARSE_MODEL_NAME),
                using=SPARSE_VECTOR_NAME,
                limit=top_k,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
    )

    chunks: list[ScoredChunk] = [
        ScoredChunk(
            chunk=Chunk.from_payload(point.payload or {}),
            score=point.score,
        )
        for point in search_result.points
    ]
    if not chunks:
        return []

    if with_rerank:
        chunks = await _rerank_chunks(query, chunks)

    if with_expansion:
        expanded_chunks = await _expand_chunks(chunks)
        chunks.extend(expanded_chunks)
    return chunks
