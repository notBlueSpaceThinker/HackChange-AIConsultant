import time
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import BaseModel, Field


class BaseProfiler(BaseModel):
    @contextmanager
    def measure(self, field: str) -> Iterator[None]:
        if field not in type(self).model_fields:
            raise AttributeError(f"{type(self).__name__} has no field '{field}'")
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            setattr(self, field, (getattr(self, field) or 0.0) + elapsed)


class RagProfiler(BaseProfiler):
    embedding_time: float | None = Field(default=None, ge=0, description="Embedding model, seconds")
    reranking_time: float | None = Field(default=None, ge=0, description="Reranker, seconds")
    generation_time: float | None = Field(default=None, ge=0, description="Main LLM, seconds")
    rag_time: float | None = Field(default=None, ge=0, description="Whole RAG pipeline, seconds")


class SummarizerProfiler(BaseProfiler):
    summarizer_time: float | None = Field(default=None, ge=0, description="Summarizer LLM, seconds")
