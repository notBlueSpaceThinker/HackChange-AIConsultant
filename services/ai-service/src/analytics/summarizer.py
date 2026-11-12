from src.core.llm import generate_response
from src.schemas.domain.state import Message

SUMMARIZE_PROMPT = """
    Ты - ассистент компании Energytool.
    К тебе обращается пользователь.
    Составь структурированное резюме проблемы пользователя.
    Учитывай прошлое сообщение.
    Сохраняй ранее известные факты.
    Не переписывай резюме заново.
    Дополняй резюме новыми деталями из последних сообщений.
    Выдай ответ в формате:
    1. Проблема клиента в формате 1-2 предложений.
    2. Параметры объекта (мощность, регион, счётчики).
    3. Рекомендованное решение от компании.
    """


async def run_pipeline(
    message: Message,
    history: list[Message] | None = None,
    summary: str | None = None,
) -> str:
    parts = []
    if summary:
        parts.append(f"Прошлое резюме: {summary}")
    parts.append(f"Новое сообщение: {message.content}")
    parts.append("Обновленное резюме:")
    prompt = "\n\n".join(parts)
    raw_answer = await generate_response(
        prompt=prompt,
        history=history,
        system_prompt=SUMMARIZE_PROMPT,
        temperature=0.0,
        think=False,
    )
    return raw_answer.strip()
