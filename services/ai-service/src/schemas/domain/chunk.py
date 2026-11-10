from llama_index.core.schema import TextNode
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from enum import StrEnum
from typing import Any

class SectionType(StrEnum):
    OVERVIEW = "overview"
    RESTRICTION = "restriction"
    FAQ = "faq"
    FACTS = "facts"
    REQUIREMENTS = "requirements"
    PROCESS = "process"

class ChunkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    h5: str | None = None
    h6: str | None = None
    breadcrumbs: str = ""
    section_type: SectionType = SectionType.OVERVIEW
    chunk_index: int = Field(default=0, ge=0)


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID = Field(default_factory=uuid4)
    text: str
    metadata: ChunkMetadata

    def to_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata.model_dump(mode="json")
        }

    def to_llama_node(self) -> TextNode:
        return TextNode(
            text=self.text,
            metadata=self.metadata.model_dump(mode="json"),
        )
