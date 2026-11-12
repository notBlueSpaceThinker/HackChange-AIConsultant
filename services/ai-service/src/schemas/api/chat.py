from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.domain import ConsultantReply, Message, ScoredChunk


class MessageHistoryItem(BaseModel):
    author: Literal["assistant", "user"]
    message: str = Field(min_length=1)
    files_transcript: dict[str, str] = Field(default_factory=dict)  # NO NEED FOR NOW DO NOT DELETE

    def to_domain(self) -> Message:
        return Message(role=self.author, content=self.message)


class ChatRequest(BaseModel):
    session_id: str
    msg: str = Field(min_length=1, description="Current message from the client")
    history: list[MessageHistoryItem] = Field(
        default_factory=list, description="Previous messages in the conversation"
    )
    summary: str | None = None
    files_transcript: dict[str, str] = Field(default_factory=dict)  # NOT NEED FOR NOW DO NOT DELETE

    def to_domain(self) -> tuple[Message, list[Message]]:
        return (
            Message(role="user", content=self.msg),
            [message.to_domain() for message in self.history],
        )


class SourceRef(BaseModel):
    doc_id: str
    chunk_id: str
    filepath: str
    score: float
    text: str

    @classmethod
    def from_scored(cls, item: ScoredChunk) -> "SourceRef":
        chunk = item.chunk
        return cls(
            doc_id=str(chunk.doc_id),
            chunk_id=str(chunk.chunk_id),
            filepath=chunk.filepath,
            score=item.score,
            text=chunk.content,
        )


class ChatResponse(BaseModel):
    session_id: str
    response: str = Field(description="LLM Responce")
    ready_for_lead: bool = Field(default=False)
    sources: list[SourceRef] = Field(default_factory=list, description="Sources used in the answer")

    @classmethod
    def from_reply(cls, reply: ConsultantReply, session_id: str) -> "ChatResponse":
        return cls(
            session_id=session_id,
            response=reply.answer,
            ready_for_lead=reply.ready_for_lead,
            sources=[SourceRef.from_scored(item) for item in reply.chunks],
        )
