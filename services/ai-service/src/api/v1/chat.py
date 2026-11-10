import logging
import time

from fastapi import APIRouter

from src.schemas.api.chat import ChatRequest, ChatResponse
from src.schemas.domain import ConfidenceStatus, ConsultantReply, DialogState, Message

router = APIRouter(prefix="/api/v1", tags=["chat"])
log = logging.getLogger(__name__)

FALLBACK_ANSWER = "Не могу ответить по доступным материалам. Могу передать вопрос специалисту - оставите контакты?"


# TODO: заглушка. Заменить на run_pipeline из src/rag/pipeline.py (Артемиюю).
def run_pipeline(messages: list[Message]) -> ConsultantReply:
    return ConsultantReply(
        answer="Здесь будет ответ консультанта.",
        state=DialogState(confidence_status=ConfidenceStatus.answered),
    )


@router.post("/chat")
def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    try:
        reply = run_pipeline(request.to_messages())
    except Exception:
        log.exception("pipeline упал")
        reply = ConsultantReply(
            answer=FALLBACK_ANSWER,
            state=DialogState(confidence_status=ConfidenceStatus.out_of_scope),
        )
    reply.timings.total_ms = int((time.perf_counter() - started) * 1000)
    return ChatResponse.from_reply(reply)