import re
from typing import List
from src.schemas.domain.chunk import Document

def clean_cell_text(text: str) -> str:
    """
    Очищает текст отдельной ячейки таблицы или текстового фрагмента:
    - Заменяет любые переводы строк (\\r\\n, \\n, \\r) на пробелы
    - Схлопывает множественные пробелы и табы в один пробел
    - Удаляет пробельные символы по краям текста
    - Вырезает мусорные символы разметки, если ячейка пустая ('|---|')
    """
    if not text:
        return ""

    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

    text = re.sub(r'[\s\t]+', ' ', text)

    text = text.strip()

    if re.match(r'^[-\s:|]+$', text):
        return ""

    return text


def clean_documents(documents: List[Document]) -> List[Document]:
    """
    Дополнительная функция полной очистки текстового контента документов.
    Убирает дублирующиеся пустые строки, сохраняя логические абзацы.
    """
    for doc in documents:
        text = doc.page_content

        text = re.sub(r'\n{3,}', '\n\n', text)

        text = "\n".join([line.rstrip() for line in text.split("\n")])

        text = text.replace(r'\##', '##').replace(r'\#', '#')
        
        doc.page_content = text.strip()
        
    return documents
