from src.schemas.domain.state import Message


async def summarize(
    message: Message,
    history: list[Message],
    previous_summary: str | None,
    answer: str,
) -> str:
    return previous_summary or ""