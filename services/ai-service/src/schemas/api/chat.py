from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.domain import ConfidenceStatus, ConsultantReply, Message, ScoredChunk, Timings

AUTHOR_TO_ROLE = {"user": "user", "llm": "assistant"}


class MessageHistoryItem(BaseModel):
    author: Literal["llm", "user"] = Field(description="Автор сообщения: user (клиент) или llm (бот)")
    message: str = Field(min_length=1, max_length=8000, description="Текст сообщения")
    files_trainscript: dict[str, str] = Field(
        default_factory=dict,
        description="Расшифровки файлов: имя файла -> текст (например, {'123.png': '...'})",
    )

    def to_domain(self) -> Message:
        return Message(role=AUTHOR_TO_ROLE[self.author], content=self.message, files=self.files_trainscript)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="Текущее сообщение клиента")
    history: list[MessageHistoryItem] = Field(
        default_factory=list,
        description="Предыдущие сообщения диалога",
    )
    files_trainscript: dict[str, str] = Field(
        default_factory=dict,
        description="Расшифровки файлов: имя файла -> текст (например, {'123.png': '...'})",
    )

    def to_messages(self) -> list[Message]:
        current = Message(role="user", content=self.message, files=self.files_trainscript)
        return [item.to_domain() for item in self.history] + [current]


class SourceRef(BaseModel):
    doc_id: str
    source_file: str
    title: str
    section_path: str
    score: float
    text: str

    @classmethod
    def from_scored(cls, item: ScoredChunk) -> "SourceRef":
        chunk = item.chunk
        return cls(
            doc_id=str(chunk.doc_id),
            source_file=chunk.source_file,
            title=chunk.title,
            section_path=chunk.section_path,
            score=item.score,
            text=chunk.content,
        )


class ChatResponse(BaseModel):
    message: str = Field(description="Ответ консультанта")
    status: ConfidenceStatus = Field(
        default=ConfidenceStatus.answered,
        description="answered - ответ найден, need_clarification - уточнить, out_of_scope - не по теме",
    )
    ready_for_lead: bool = Field(
        default=False, description="true - клиент готов оставить заявку, нужно показать форму контактов"
    )
    sources: