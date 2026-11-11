from typing import Literal

from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel, Field

from src.schemas.domain import ConfidenceStatus, ConsultantReply, Message, ScoredChunk, Timings

AUTHOR_TO_ROLE = {"user": "user", "LLM": "assistant"}


def _format_text_with_files(text: str, files: dict[str, str]) -> str:
    clean_text = text.strip()
    if not files:
        return clean_text
    files_block = "\n".join(f"- {name}: {content}" for name, content in files.items())
    return f"{clean_text}\n\n[Расшифровка приложенных файлов:\n{files_block}]"


class MessageHistoryItem(BaseModel):
    author: Literal["LLM", "user"] = Field(
        description="Автор сообщения: user (клиент) или LLM (бот)"
    )
    message: str = Field(min_length=1, max_length=8000, description="Текст сообщения")
    files_transcript: dict[str, str] = Field(
        default_factory=dict,
        description="Расшифровки файлов: имя файла -> текст (например, {'123.png': '...'})",
    )

    def to_domain(self) -> Message:
        return Message(
            role=AUTHOR_TO_ROLE[self.author], content=self.message, files=self.files_transcript
        )

    def to_llama_message(self) -> ChatMessage:
        return ChatMessage(
            role=MessageRole.USER if self.author == "user" else MessageRole.ASSISTANT,
            content=_format_text_with_files(self.message, self.files_transcript),
        )


class ChatRequest(BaseModel):
    msg: str = Field(min_length=1, max_length=8000, description="Текущее сообщение клиента")
    history: list[MessageHistoryItem] = Field(
        default_factory=list,
        description="Предыдущие сообщения диалога",
    )
    files_transcript: dict[str, str] = Field(
        default_factory=dict,
        description="Расшифровки файлов: имя файла -> текст (например, {'123.png': '...'})",
    )

    def to_messages(self) -> list[Message]:
        current = Message(role="user", content=self.msg, files=self.files_transcript)
        return [item.to_domain() for item in self.history] + [current]

    def to_llama_inputs(self) -> tuple[str, list[ChatMessage]]:
        query = _format_text_with_files(self.msg, self.files_transcript)
        history = [item.to_llama_message() for item in self.history]
        return query, history


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
    response: str = Field(description="Ответ консультанта")
    status: ConfidenceStatus = Field(
        default=ConfidenceStatus.answered,
        description="answered - ответ найден, "
        "need_clarification - уточнить, out_of_scope - не по теме",
    )
    ready_for_lead: bool = Field(
        default=False,
        description="true - клиент готов оставить заявку, нужно показать форму контактов",
    )
    sources: list[SourceRef] = Field(
        default_factory=list,
        description="Документы базы знаний, использованные в ответе (для режима отладки)",
    )
    timings: Timings = Field(
        default_factory=Timings, description="Время этапов в миллисекундах (для режима отладки)"
    )

    @classmethod
    def from_reply(cls, reply: ConsultantReply) -> "ChatResponse":
        return cls(
            response=reply.answer,
            status=reply.state.confidence_status,
            ready_for_lead=reply.state.is_ready_for_lead,
            sources=[SourceRef.from_scored(item) for item in reply.chunks],
            timings=reply.timings,
        )
