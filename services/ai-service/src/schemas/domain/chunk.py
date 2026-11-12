from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

KB_NAMESPACE = UUID("6f1c2b0e-8a4d-4c3e-9b7a-2d5e1f0a9c41")


def make_doc_id(filepath: str) -> UUID:
    return uuid5(KB_NAMESPACE, filepath.replace("\\", "/").strip("/"))


def make_chunk_id(doc_id: UUID, chunk_index: int) -> UUID:
    return uuid5(doc_id, str(chunk_index))


class KBDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: UUID
    filepath: str
    filename: str
    content: str = Field(min_length=1)

    @classmethod
    def from_file(cls, filepath: str, content: str) -> "KBDocument":
        path = filepath.replace("\\", "/").strip("/")
        return cls(
            doc_id=make_doc_id(path),
            filepath=path,
            filename=path.rsplit("/", 1)[-1],
            content=content,
        )


class SectionType(StrEnum):
    OTHER = "other"
    RESTRICTION = "restriction"
    FAQ = "faq"
    FACTS = "facts"
    REQUIREMENTS = "requirements"
    PROCESS = "process"


class ChunkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    h5: str | None = None
    h6: str | None = None
    section_type: SectionType = SectionType.OTHER
    section_path: str = Field(default="", description="Headings separated by ' > '")


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    doc_id: UUID
    filepath: str
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Chunk":
        return cls.model_validate(payload)


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float
