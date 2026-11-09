from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(description="'user' или 'assistant'")
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: List[ChatMessage] = Field(default_factory=list)

class SourceDocInfo(BaseModel):
    """Что видит оператор/жюри в режиме отладки (требование кейса МТС)."""
    doc_name: str
    section: str
    excerpt: str
    score: float

class ChatResponse(BaseModel):
    answer: str
    # Если режим отладки выключен, debug_info может быть None
    debug_sources: Optional[List[SourceDocInfo]] = None
    latency_ms: Optional[float] = None
