from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from llama_index.core.schema import TextNode
from pydantic import BaseModel, ConfigDict, Field

KB_NAMESPACE = UUID("6f1c2b0e-8a4d-4c3e-9b7a-2d5e1f0a9c41")


def make_doc_id(source_file: str) -> UUID:
    return uuid5(KB_NAMESPACE, source_file.replace("\\", "/").strip("/"))


def make_chunk_id(doc_id: UUID, chunk_index: int) -> UUID:
    return uuid5(doc_id, str(chunk_index))


class SectionType(StrEnum):
    OVERVIEW = "overview"
    RESTRICTION = "restriction"
    FAQ = "faq"
    FACTS = "facts"
    REQUIREMENTS = "requirements"
    PROCESS = "process"


class KBDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: UUID
    source_file: str = Field(description="Путь в БЗ, например 20-products/21-orem.md")
    filename: str = Field(description="Имя файла, например 21-orem.md")
    category: str = Field(description="Папка верхнего уровня: 00-reference, 10-energy, 20-products")
    title: str = Field(description="Главный заголовок документа (# ...)")
    product_name: str | None = Field(
        default=None, description="Название продукта для 20-products/*"
    )
    content: str = Field(min_length=1)

    @classmethod
    def from_file(
        cls, source_file: str, title: str, content: str, product_name: str | None = None
    ) -> "KBDocument":
        path = source_file.replace("\\", "/").strip("/")
        parts = path.split("/")
        return cls(
            doc_id=make_doc_id(path),
            source_file=path,
            filename=parts[-1],
            category=parts[0] if len(parts) > 1 else "",
            title=title,
            product_name=product_name,
            content=content,
        )


class ChunkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    h5: str | None = None
    h6: str | None = None
    section_type: SectionType = SectionType.OVERVIEW


class DocumentChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    doc_id: UUID = Field(description="Ссылка на документ в PostgreSQL, чтобы открыть первоисточник")
    source_file: str
    category: str = ""
    title: str = ""
    product_name: str | None = None
    section_path: str = Field(default="", description="Заголовки через ' > '")
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    hype_questions: list[str] = Field(default_factory=list, description="HyPE-вопросы к чанку")
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

    @property
    def text(self) -> str:
        """Алиас для обратной совместимости."""
        return self.content

    @classmethod
    def from_document(
        cls,
        doc: KBDocument,
        chunk_index: int,
        content: str,
        section_path: str = "",
        metadata: ChunkMetadata | None = None,
    ) -> "DocumentChunk":
        return cls(
            chunk_id=make_chunk_id(doc.doc_id, chunk_index),
            doc_id=doc.doc_id,
            source_file=doc.source_file,
            category=doc.category,
            title=doc.title,
            product_name=doc.product_name,
            section_path=section_path,
            chunk_index=chunk_index,
            content=content,
            metadata=metadata or ChunkMetadata(),
        )

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DocumentChunk":
        return cls.model_validate(payload)

    def as_context(self) -> str:
        header = " > ".join(part for part in (self.title, self.section_path) if part)
        return f"[{self.source_file}] {header}\n{self.content}"

    def to_llama_node(self) -> TextNode:
        payload = self.to_payload()
        excluded_keys = [
            "chunk_id",
            "doc_id",
            "source_file",
            "category",
            "title",
            "product_name",
            "section_path",
            "chunk_index",
            "hype_questions",
            "metadata",
        ]
        return TextNode(
            id_=str(self.chunk_id),
            text=self.content,
            metadata=payload,
            excluded_embed_metadata_keys=excluded_keys,
            excluded_llm_metadata_keys=["chunk_id", "doc_id", "metadata"],
        )
