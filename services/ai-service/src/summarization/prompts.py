import json

from src.schemas.domain.state import ClientProfile, Product

CLIENT_PROFILE_SCHEMA = json.dumps(ClientProfile.model_json_schema())

PRODUCT_VALUES = ", ".join([f"'{p.value}'" for p in Product])


class SummaryPrompt:
    SYSTEM_PROMPT: str = """
Ты - бот суммаризатор компании Energytool.
Твоя задача — вести актуальное структурированное саммари диалога с клиентом.
На вход ты получаешь текущее саммари (если оно уже есть) и новые сообщения из диалога.        Составь структурированное резюме проблемы пользователя.
Правила обновления саммари:
1. Учитывай прошлое сообщение.
2. Сохраняй все ранее зафиксированные факты, если они не были опровергнуты.
3. дополняй пункты новыми деталями из последних сообщений.
4. Если в новых сообщениях клиент уточнил или изменил старые данные (например, мощность или регион) — обнови их на актуальные.
5. Не выдумывай данные. Если информации по пункту ещё нет в диалоге, пиши строго: 'Не указано'.
6. Выводи только само саммари без приветствий, комментариев и вводных слов.

Выдай ответ в формате:
1. Проблема клиента в формате 1-2 предложений.
2. Параметры объекта (мощность, регион, счётчики).
3. Рекомендованное решение от компании.
    """
    prompt_template = """
Текущее саммари:
{previous_summary}

Новое сообщеие от пользователя:
{user_message}

Ответ от бота-помошника:
{assistant_message}
    """

    @classmethod
    def format_user_prompt(
        cls,
        user_message: str,
        assistant_message: str,
        previous_summary: str | None = None,
    ) -> str:
        return cls.prompt_template.format(
            user_message=user_message.strip(),
            assistant_message=assistant_message.strip(),
            previous_summary=previous_summary.strip() if previous_summary else "",
        )
