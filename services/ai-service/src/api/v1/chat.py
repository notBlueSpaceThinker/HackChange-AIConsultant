import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.rag.pipeline import run_rag_pipeline
from src.rag.retriever import get_document_chunks
from src.schemas.api.chat import (
    ChatRequest,
    ChatResponse,
    DocumentChunkRef,
    DocumentResponse,
    SummarizerRequest,
    SummarizerResponse,
)
from src.schemas.domain.state import ConsultantReply, SummarizerReply
from src.summarization.pipeline import run_summarizer_pipeline

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "Хороший вопрос, но точного ответа у меня нет. "
    "Оставьте контакты, и наш специалист с вами свяжется."
)


@router.post("/completions")
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        message, history = request.to_domain()
        reply = await run_rag_pipeline(message, history, request.summary)
    except Exception:
        log.exception("pipeline упал")  # :(
        reply = ConsultantReply(
            answer=FALLBACK_ANSWER,
            ready_for_lead=True,
        )

    log.info(
        "chat completed session_id=%s ready_for_lead=%s",
        request.session_id,
        reply.ready_for_lead,
    )
    return ChatResponse.from_reply(reply, session_id=request.session_id)


@router.post("/summarize")
async def summarize(request: SummarizerRequest) -> SummarizerResponse:
    try:
        reply = await run_summarizer_pipeline(
            user_message=request.user_message,
            assistant_message=request.assistant_message,
            summary=request.summary,
        )
    except Exception:
        log.exception("summarizer pipeline упал session_id=%s", request.session_id)
        reply = SummarizerReply(summary=request.summary or "")
    log.info("summarize completed session_id=%s", request.session_id)
    return SummarizerResponse(
        session_id=request.session_id,
        summary=reply.summary,
        profiler=reply.profiler,
    )


@router.get("/documents/{doc_id}")
async def get_document(doc_id: UUID) -> DocumentResponse:
    chunks = await get_document_chunks(str(doc_id))
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(
        doc_id=str(doc_id),
        filepath=chunks[0].filepath,
        chunks=[DocumentChunkRef.from_chunk(chunk) for chunk in chunks],
    )
