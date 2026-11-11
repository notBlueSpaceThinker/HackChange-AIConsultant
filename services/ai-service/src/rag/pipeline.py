import time

from src.core.llm import generate_response
from src.rag.prompts import ConsultantPrompt, IrrelevantContext
from src.rag.retriever import retrieve
from src.schemas.api.chat import ChatRequest
from src.schemas.domain.chunk import DocumentChunk
from src.schemas.domain.search import ScoredChunk
from src.schemas.domain.state import (
    ConfidenceStatus,
    ConsultantReply,
    DialogState,
    Timings,
)


def _format_document_chunk(document_chunk: DocumentChunk | ScoredChunk) -> str:
    if isinstance(document_chunk, ScoredChunk):
        document_chunk = document_chunk.chunk
    return document_chunk.as_context()


def _format_context(context: list[DocumentChunk | ScoredChunk]) -> str:
    return "\n=======\n".join(_format_document_chunk(chunk) for chunk in context)


async def run_pipeline(request: ChatRequest) -> ConsultantReply:
    """
    Runs the RAG pipeline.
    """
    query, history = request.to_llama_inputs()

    t_ret = time.perf_counter()
    chunks = await retrieve(query)
    retrieval_ms = int((time.perf_counter() - t_ret) * 1000)

    context = _format_context(chunks) if chunks else IrrelevantContext.PROMPT
    prompt = ConsultantPrompt.format_user_prompt(query=query, context=context)

    t_llm = time.perf_counter()
    answer = await generate_response(
        prompt=prompt,
        history=history,
        system_prompt=ConsultantPrompt.SYSTEM_PROMPT,
    )
    llm_ms = int((time.perf_counter() - t_llm) * 1000)

    status = ConfidenceStatus.answered if chunks else ConfidenceStatus.out_of_scope
    return ConsultantReply(
        answer=answer,
        state=DialogState(confidence_status=status),
        chunks=chunks,
        timings=Timings(retrieval_ms=retrieval_ms, llm_ms=llm_ms),
    )
