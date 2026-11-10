from pydantic import BaseModel, Field
from typing import Dict, Any

class Document(BaseModel):
    """
    Официальная схема документа базы знаний для хакатона МТС True Tech.
    Используется для передачи данных по цепочке: loader -> cleaner -> linearizer.
    """
    page_content: str = Field(
        ..., 
        description="Текст документа (исходный или прошедший очистку/линеаризацию таблиц)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь метаданных документа: category, filename, product_name"
    )

    @property
    def category(self) -> str:
        """Хелпер для быстрого доступа к категории из метаданных."""
        return self.metadata.get("category", "unknown")

    @property
    def filename(self) -> str:
        """Хелпер для быстрого доступа к имени файла."""
        return self.metadata.get("filename", "")

    @property
    def product_name(self) -> str:
        """Хелпер для быстрого доступа к названию продукта/заголовку."""
        return self.metadata.get("product_name", "Без названия")

    #потом удалить, чисто для меня, чтобы проверять
    def to_dict(self) -> dict:
        return {
            "page_content": self.page_content,
            "metadata": self.metadata
        }