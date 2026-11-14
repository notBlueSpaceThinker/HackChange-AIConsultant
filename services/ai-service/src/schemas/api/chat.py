from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.domain.chunk import ScoredChunk
from src.schemas.domain.state import ConsultantReply, Message


class MessageHistoryItem(BaseModel):
    author: Literal["assistant", "user"]
    message: str = Field(min_length=1)
    files_transcript: dict[str, str] = Field(default_factory=dict)

    def to_domain(self) -> Message:
        return Message(role=self.author, content=self.message)


class ChatRequest(BaseModel):
    session_id: str = Field(description="Номер диалога")
    msg: str = Field(min_length=1, description="Текущее сообщение клиента")
    history: list[MessageHistoryItem] = Field(
        default_factory=list, description="Предыдущие сообщения диалога"
    )
    summary: str | None = Field(default=None, description="Сводка диалога для менеджера")
    files_transcript: dict[str, str] = Field(default_factory=dict)

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
    session_id: str = Field(description="Номер диалога")
    response: str = Field(description="Ответ ассистента")
    ready_for_lead: bool = Field(default=False, description="Бот готов собрать заявку")
    summary: str | None = Field(
        default=None, description="Обновлённая сводка диалога для менеджера"
    )
    sources: list[SourceRef] = Field(
        default_factory=list, description="Источники, использованные в ответе"
    )

    @classmethod
    def from_reply(
        cls,
        reply: ConsultantReply,
        session_id: str,
        summary: str | None = None,
    ) -> "ChatResponse":
        return cls(
            session_id=session_id,
            response=reply.answer,
            ready_for_lead=reply.ready_for_lead,
            summary=summary,
            sources=[SourceRef.from_scored(item) for item in reply.chunks],
        )


class SummarizerRequest(BaseModel):
    session_id: str
    user_message: str
    assistant_message: str
    summary: str | None = None


class SummarizerResponse(BaseModel):
    session_id: str
    summary: str
