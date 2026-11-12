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


async def build_lead_summary(messages: list[Message], previous_summary: str | None = None) -> str:
    last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
    if not last_user_msg:
        return previous_summary
    parts = []
    if previous_summary:
        parts.append(f"Прошлое резюме: {previous_summary}")
    parts.append(f"Новое сообщение: {last_user_msg}")
    parts.append("Обновленное резюме:")
    user_prompt = "\n\n".join(parts)
    answer = await generate_response(prompt=user_prompt, system_prompt=SUMMARIZE_PROMPT)
    return answer.strip()
