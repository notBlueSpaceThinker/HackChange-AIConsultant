from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.domain.chunk import ScoredChunk
from src.schemas.domain.profiler import RagProfiler, SummarizerProfiler


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ConsultantReply(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)
    ready_for_lead: bool = False
    chunks: list[ScoredChunk] = Field(default_factory=list)
    profiler: RagProfiler = Field(default_factory=RagProfiler)


class SummarizerReply(BaseModel):
    summary: str
    profiler: SummarizerProfiler = Field(default_factory=SummarizerProfiler)
