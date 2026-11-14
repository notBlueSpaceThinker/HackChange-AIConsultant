from src.core.llm import generate_response
from src.rag.prompts import ConsultantPrompt
from src.rag.retriever import retrieve
from src.schemas.domain.chunk import Chunk, ScoredChunk
from src.schemas.domain.state import ConsultantReply, Message

EMPTY_CONTEXT = "Релевантные фрагменты в базе знаний не найдены."


def _format_chunk(item: Chunk | ScoredChunk) -> str:
    chunk = item.chunk if isinstance(item, ScoredChunk) else item
    section_path = chunk.metadata.section_path
    body = chunk.content
    if section_path and body.startswith(section_path):
        body = body.removeprefix(section_path).lstrip("\n")
    header = f"[{chunk.filepath}] {section_path}".strip()
    return f"{header}\n{body}"


def _format_context(chunks: list[Chunk] | list[ScoredChunk]) -> str:
    return "\n=======\n".join(_format_chunk(chunk) for chunk in chunks)


async def run_rag_pipeline(
    message: Message,
    history: list[Message] | None = None,
    summary: str | None = None,
) -> ConsultantReply:
    """
    Run the RAG pipeline.
    """
    query = message.content
    chunks = await retrieve(query)

    context = _format_context(chunks) if chunks else EMPTY_CONTEXT
    prompt = ConsultantPrompt.format_prompt(
        query=query,
        context=context,
        summary=summary,
    )

    raw_answer = await generate_response(
        prompt=prompt,
        history=history,
        system_prompt=ConsultantPrompt.SYSTEM_PROMPT,
    )

    ready_for_lead = ConsultantPrompt.LEAD_MARKER in raw_answer
    answer = raw_answer.replace(ConsultantPrompt.LEAD_MARKER, "").strip()
    if not answer:
        answer = "Пожалуйста, заполните форму контактов, и наш специалист свяжется с вами."

    return ConsultantReply(
        answer=answer,
        ready_for_lead=ready_for_lead,
        chunks=chunks,
    )
