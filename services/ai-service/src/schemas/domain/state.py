from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.domain.chunk import ScoredChunk


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ConsultantReply(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)
    ready_for_lead: bool = False
    chunks: list[ScoredChunk] = Field(default_factory=list)
