from functools import lru_cache

import httpx

from src.config import settings


class MockReranker:
    def __init__(self, top_n: int) -> None:
        self.top_n = top_n

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        limit = min(len(documents), top_n or self.top_n)
        return [(i, round(1.0 / (i + 1), 4)) for i in range(limit)]


class Reranker:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        top_n: int,
        timeout: float,
        max_retries: int,
    ) -> None:
        self.model = model
        self.top_n = top_n
        self._client = httpx.AsyncClient(
            base_url=api_base.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=httpx.AsyncHTTPTransport(retries=max_retries),
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        limit = min(len(documents), top_n or self.top_n)
        response = await self._client.post(
            "/rerank",
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": limit,
            },
        )
        response.raise_for_status()
        body = response.json()
        entries = body.get("results") or body.get("data", [])
        results = sorted(
            entries,
            key=lambda item: float(item.get("relevance_score", item.get("score", 0.0))),
            reverse=True,
        )
        return [
            (int(item["index"]), float(item.get("relevance_score", item.get("score", 0.0))))
            for item in results[:limit]
        ]


@lru_cache
def get_reranker() -> MockReranker | Reranker:
    if settings.is_reranker_mock:
        return MockReranker(top_n=settings.reranker.top_n)
    return Reranker(
        api_base=settings.reranker.url,
        api_key=settings.reranker.api_key,
        model=str(settings.reranker.model),
        top_n=settings.reranker.top_n,
        timeout=settings.reranker.timeout,
        max_retries=settings.reranker.max_retries,
    )


async def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[tuple[int, float]]:
    if not documents:
        return []
    reranker = get_reranker()
    return await reranker.rerank(query, documents, top_n)
