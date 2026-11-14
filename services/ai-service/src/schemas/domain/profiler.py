import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from pydantic import BaseModel, Field

ProfilerField = Literal[
    "generation_time",
    "embedding_time",
    "reranking_time",
    "rag_time",
    "summarizer_time",
]


class Profiler(BaseModel):
    generation_time: float | None = Field(default=None, ge=0, description="Main LLM, seconds")
    embedding_time: float | None = Field(default=None, ge=0, description="Embedding model, seconds")
    reranking_time: float | None = Field(default=None, ge=0, description="Reranker, seconds")
    rag_time: float | None = Field(default=None, ge=0, description="Whole RAG pipeline, seconds")
    summarizer_time: float | None = Field(default=None, ge=0, description="Summarizer LLM, seconds")

    @contextmanager
    def measure(self, field: ProfilerField) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            setattr(self, field, (getattr(self, field) or 0.0) + elapsed)
