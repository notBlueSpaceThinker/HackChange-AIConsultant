from pydantic import BaseModel, Field


class MessageHistoryItem(BaseModel):
    author: str = Field(description="Message author (llm or user)")
    message: str = Field(description="Text message")
    files_trainscript: dict[str, str] = Field(
        default_factory=dict,
        description="Filenames with trainscript files (e.g. {'123.png': 'trainscription'})",
    )


class ChatRequest(BaseModel):
    message: str = Field(description="Current user message")
    history: list[MessageHistoryItem] = Field(
        default_factory=list,
        description="History of previous messages",
    )
    files_trainscript: dict[str, str] = Field(
        default_factory=dict,
        description="Filenames with trainscript files (e.g. {'123.png': 'trainscription'})",
    )


class ChatResponse(BaseModel):
    message: str = Field(description="AI response message")
