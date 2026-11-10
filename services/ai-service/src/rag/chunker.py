import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkMetadata:
    document_uuid: str
    h1: str | None
    h2: str | None
    h3: str | None
    h4: str | None
    h5: str | None
    h6: str | None
    breadcrumbs: str
    section_type: str
    chunk_index: int

@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    metadata: ChunkMetadata