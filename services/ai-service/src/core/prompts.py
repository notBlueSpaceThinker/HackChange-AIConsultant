import json

from src.schemas.domain.state import ClientProfile, Product

CLIENT_PROFILE_SCHEMA = json.dumps(ClientProfile.model_json_schema())

PRODUCT_VALUES = ", ".join([f"'{p.value}'" for p in Product])


class SummaryPrompt:
    system: str = """
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

    @staticmethod
    def format_user_prompt(
        transcript: str, profile_json: str, previous_summary: str | None = None
    ) -> str:
        parts = []
        if previous_summary:
            parts.append(f"Прошлое резюме: {previous_summary}")
        parts.append(f"Известные данные: {profile_json}")
        parts.append(f"Новое сообщение: {transcript}")
        parts.append("Обновленное резюме:")
        return "\n\n".join(parts)
