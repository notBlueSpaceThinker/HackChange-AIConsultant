import logging
import time

from fastapi import APIRouter

from src.rag.pipeline import run_pipeline
from src.schemas.api.chat import ChatRequest, ChatResponse
from src.schemas.domain.state import ConsultantReply

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "Хороший вопрос, но точного ответа у меня нет. "
    "Оставьте контакты, и наш специалист с вами свяжется."
)


@router.post("/completions")
async def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    try:
        message, history = request.to_domain()
        reply = await run_pipeline(message, history, request.summary)
    except Exception:
        log.exception("pipeline упал")  # :(
        reply = ConsultantReply(
            answer=FALLBACK_ANSWER,
            ready_for_lead=True,
        )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "chat completed session_id=%s ready_for_lead=%s elapsed_ms=%d",
        request.session_id,
        reply.ready_for_lead,
        elapsed_ms,
    )
    return ChatResponse.from_reply(reply, session_id=request.session_id)
