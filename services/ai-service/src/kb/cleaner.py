import re

from src.schemas.domain.chunk import KBDocument


def clean_cell_text(text: str) -> str:
    """
    [A-2] Очищает текст отдельной ячейки таблицы или фрагмента:
    - Заменяет переводы строк на пробелы
    - Схлопывает множественные пробелы и табы
    - Убирает пробелы по краям и пустую разметку таблицы
    """
    if not text:
        return ""

    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"[\s\t]+", " ", text).strip()

    if re.match(r"^[-\s:|]+$", text):
        return ""

    return text


def clean_text(text: str) -> str:
    """Очищает полный текст документа от лишних пустых строк и экранирования заголовков."""
    text = text.replace(r"\##", "##").replace(r"\#", "#")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def clean_documents(documents: list[KBDocument]) -> list[KBDocument]:
    """Возвращает новый список KBDocument с очищенным полем content."""
    return [doc.model_copy(update={"content": clean_text(doc.content)}) for doc in documents]
