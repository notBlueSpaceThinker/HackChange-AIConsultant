from pydantic import BaseModel

from src.schemas.domain.chunk import DocumentChunk


class ScoredChunk(BaseModel):
    chunk: DocumentChunk
    dense_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None

    @property
    def score(self) -> float:
        for value in (self.rerank_score, self.rrf_score, self.dense_score, self.bm25_score):
            if value is not None:
                return value
        return 0.0
