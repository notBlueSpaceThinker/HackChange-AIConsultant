import json

from src.schemas.domain.state import ClientProfile, Message, Product

EXTRACTED_FIELDS = ("problem_summary", "target_product", "phone")


def _build_schema() -> str:
    schema = ClientProfile.model_json_schema()
    schema["properties"] = {
        name: spec for name, spec in schema["properties"].items() if name in EXTRACTED_FIELDS
    }
    schema["required"] = []
    return json.dumps(schema, ensure_ascii=False, indent=2)


_PROFILE_SCHEMA = _build_schema()
_PRODUCTS = " / ".join(p.value for p in Product)


class ClientExtractorPrompt:
    system: str = (
        """Ты - модель для извлечения данных клиента из истории диалога.
        Тебе нужно понять проблему клиента и подобрать продукт.
        Правила:
        1. Возвращай данные клиента в формате JSON без лишнего текста вокруг.
        2. Если клиент не упомянул часть информации, не придумывай её.
        В соответствующем поле ставь значение null.
        3. Каждый раз собирай информацию из всех реплик диалога, сохраняя уже известные данные.
        Информацию бери из реплик клиента.
        4. Определяй target_product и формулируй проблему клиента (problem summary).
        Если проблема пока не ясна, значение null.
        "Схема JSON\n"
    """
        f"{_PROFILE_SCHEMA}"
    )

    @staticmethod
    def format_user_prompt(
        history: list[Message],
        known_profile: ClientProfile | None = None,
    ) -> str:
        dialog = "\n".join(
            f"{'Клиент' if m.role == 'user' else 'Ассистент'}: {m.content}" for m in history
        )
        known = (
            known_profile.model_dump_json(indent=2, include=set(EXTRACTED_FIELDS))
            if known_profile
            else "null"
        )
        return (
            f"Уже известные данные\n{known}\n\n"
            f"История диалога\n{dialog}\n\n"
            "Верни обновлённые данные в формате JSON по схеме."
        )
