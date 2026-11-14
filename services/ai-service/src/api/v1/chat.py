import logging
import time

from fastapi import APIRouter

from src.analytics.summarizer import summarize
from src.rag.pipeline import run_pipeline
from src.schemas.api.chat import ChatRequest, ChatResponse
from src.schemas.domain.state import ConsultantReply
from src.summarization.pipeline import run_summarizer_pipeline

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "Хороший вопрос, но точного ответа у меня нет. "
    "Оставьте контакты, и наш специалист с вами свяжется."
)


@router.post("/completions")
async def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    message, history = request.to_domain()
    try:
        reply = await run_pipeline(message, history, request.summary)
    except Exception:
        log.exception("pipeline упал")
        reply = ConsultantReply(
            answer=FALLBACK_ANSWER,
            ready_for_lead=True,
        )

    summary = request.summary
    if reply.ready_for_lead or request.summary:
        try:
            summary = await summarize(message, history, request.summary, reply.answer)
        except Exception:
            log.exception("summarizer упал")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "chat completed session_id=%s ready_for_lead=%s elapsed_ms=%d",
        request.session_id,
        reply.ready_for_lead,
        elapsed_ms,
    )
    return ChatResponse.from_reply(reply, session_id=request.session_id, summary=summary)
