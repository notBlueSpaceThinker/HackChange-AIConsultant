import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from llama_index.core.bridge.pydantic import Field
from llama_index.core.node_parser.interface import NodeParser
from llama_index.core.schema import BaseNode, MetadataMode, TextNode

from src.config import SRC_DIR, settings
from src.schemas.domain.chunk import (
    Chunk,
    ChunkMetadata,
    DocumentChunk,
    KBDocument,
    SectionType,
    make_chunk_id,
    make_doc_id,
)

RULES_PATH = SRC_DIR / "rag" / "section_rules.json"

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    h5: str | None = None
    h6: str | None = None
    body: str = ""

    @property
    def headings(self) -> tuple[str | None, ...]:
        return (self.h1, self.h2, self.h3, self.h4, self.h5, self.h6)


def _ensure_uuid(doc_id: UUID | str) -> UUID:
    if isinstance(doc_id, UUID):
        return doc_id
    try:
        return UUID(str(doc_id))
    except ValueError:
        return make_doc_id(str(doc_id))


@lru_cache
def load_section_rules(path: Path = RULES_PATH) -> tuple[SectionType, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    default_type = SectionType(raw.get("default_section_type", SectionType.OVERVIEW))
    rules = [
        {
            "section_type": SectionType(rule["section_type"]),
            "exact": {
                level: {x.strip().lower() for x in rule.get(f"h{level}_exact", ())}
                for level in range(1, 7)
            },
            "title_contains": [x.strip().lower() for x in rule.get("title_contains", ())],
        }
        for rule in raw.get("rules", [])
    ]
    return default_type, rules


def classify_section(headings: Sequence[str | None]) -> SectionType:
    default_type, rules = load_section_rules()
    normalized = [(h or "").strip().lower() for h in headings]
    for level in range(len(normalized), 1, -1):
        title = normalized[level - 1]
        if not title:
            continue
        for rule in rules:
            if title in rule["exact"].get(level, ()):
                return rule["section_type"]
    sub_headings = [h for h in normalized[1:] if h]
    for rule in rules:
        if any(sub in h for h in sub_headings for sub in rule["title_contains"]):
            return rule["section_type"]

    if normalized and normalized[0]:
        for rule in rules:
            if normalized[0] in rule["exact"].get(1, ()):
                return rule["section_type"]

    return default_type


def build_breadcrumbs(
    headings: Sequence[str | None],
    separator: str = " > ",
) -> str:
    return separator.join(title for title in headings if title)


def parse_markdown(text: str) -> list[MarkdownSection]:
    sections: list[MarkdownSection] = []
    headings: list[str | None] = [None] * 6
    body_lines: list[str] = []
    in_fence = False

    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            body_lines.append(line)
            continue

        if not in_fence:
            match = _HEADING_RE.match(line)
            if match:
                body = "\n".join(body_lines).strip()
                if body:
                    sections.append(MarkdownSection(*headings, body=body))
                body_lines = []

                level = len(match.group(1))
                title = match.group(2).strip()
                headings[level - 1] = title
                for idx in range(level, 6):
                    headings[idx] = None
                continue

        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if body:
        sections.append(MarkdownSection(*headings, body=body))

    return sections


def split_long_section(
    body: str,
    section_type: SectionType = SectionType.OVERVIEW,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[str]:
    if section_type == SectionType.FAQ or len(body) <= max_chars:
        return [body]

    blocks = [part.strip() for part in re.split(r"\n{2,}", body) if part.strip()]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        sub_blocks = block.splitlines() if len(block) > max_chars else [block]
        for item in sub_blocks:
            item = item.strip()
            if not item:
                continue
            sep = 2 if len(block) <= max_chars else 1
            added = len(item) if not current else len(item) + sep

            if current and current_len + added > max_chars:
                parts.append("\n\n".join(current))
                tail = current[-1] if len(current[-1]) <= overlap else ""
                current = [tail] if tail else []
                current_len = len(tail)

            current.append(item)
            current_len += len(item) if len(current) == 1 else len(item) + sep

    if current:
        parts.append("\n\n".join(current))

    return parts


def chunk_markdown(
    text: str,
    document_id: UUID | str = "",
    source_file: str = "",
    title: str = "",
    category: str = "",
    product_name: str | None = None,
    max_chunk_chars: int = settings.rag.max_chunk_chars,
    chunk_overlap: int = settings.rag.chunk_overlap,
) -> list[DocumentChunk]:
    doc_uuid = _ensure_uuid(document_id or source_file or "document")
    resolved_source_file = source_file or (str(document_id) if document_id else "")

    sections = parse_markdown(text)
    first_h1 = next((s.h1 for s in sections if s.h1), "")
    doc_title = title or first_h1

    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for section in sections:
        breadcrumbs = build_breadcrumbs(section.headings)
        section_type = classify_section(section.headings)
        prefix = f"{breadcrumbs}\n\n" if breadcrumbs else ""
        max_body = max(max_chunk_chars - len(prefix), 200)

        parts = split_long_section(
            section.body,
            section_type=section_type,
            max_chars=max_body,
            overlap=chunk_overlap,
        )
        for part in parts:
            metadata = ChunkMetadata(
                h1=section.h1,
                h2=section.h2,
                h3=section.h3,
                h4=section.h4,
                h5=section.h5,
                h6=section.h6,
                section_type=section_type,
            )
            chunk_uuid = make_chunk_id(doc_uuid, chunk_index)
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_uuid,
                    doc_id=doc_uuid,
                    source_file=resolved_source_file,
                    category=category,
                    title=doc_title,
                    product_name=product_name,
                    section_path=breadcrumbs,
                    chunk_index=chunk_index,
                    content=f"{prefix}{part}",
                    metadata=metadata,
                )
            )
            chunk_index += 1

    return chunks


def chunk_document(
    doc: KBDocument,
    max_chunk_chars: int | None = None,
    chunk_overlap: int | None = None,
) -> list[DocumentChunk]:
    return chunk_markdown(
        text=doc.content,
        document_id=doc.doc_id,
        source_file=doc.source_file,
        title=doc.title,
        category=doc.category,
        product_name=doc.product_name,
        max_chunk_chars=max_chunk_chars,
        chunk_overlap=chunk_overlap,
    )


class MarkdownChunker(NodeParser):
    max_chunk_chars: int = Field(default=settings.rag.max_chunk_chars)
    chunk_overlap: int = Field(default=settings.rag.chunk_overlap)

    def get_nodes_from_node(self, node: BaseNode) -> list[TextNode]:
        text = node.get_content(metadata_mode=MetadataMode.NONE)
        doc_id = (
            node.metadata.get("doc_id")
            or node.metadata.get("document_id")
            or node.metadata.get("file_name")
            or node.node_id
        )
        source_file = node.metadata.get("source_file") or node.metadata.get("file_name") or ""
        title = node.metadata.get("title") or ""
        category = node.metadata.get("category") or ""
        product_name = node.metadata.get("product_name")

        chunks = chunk_markdown(
            text=text,
            document_id=doc_id,
            source_file=source_file,
            title=title,
            category=category,
            product_name=product_name,
            max_chunk_chars=self.max_chunk_chars,
            chunk_overlap=self.chunk_overlap,
        )
        return [chunk.to_llama_node() for chunk in chunks]

    def _parse_nodes(
        self,
        nodes: Sequence[BaseNode],
        show_progress: bool = False,
        **kwargs: Any,
    ) -> list[BaseNode]:
        result: list[BaseNode] = []
        for node in nodes:
            result.extend(self.get_nodes_from_node(node))
        return result


__all__ = [
    "Chunk",
    "ChunkMetadata",
    "DocumentChunk",
    "MarkdownChunker",
    "MarkdownSection",
    "SectionType",
    "build_breadcrumbs",
    "chunk_document",
    "chunk_markdown",
    "classify_section",
    "load_section_rules",
    "parse_markdown",
    "split_long_section",
]
