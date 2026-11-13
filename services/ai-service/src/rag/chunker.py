import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import SRC_DIR, settings
from src.schemas.domain.chunk import (
    Chunk,
    ChunkMetadata,
    KBDocument,
    SectionType,
    make_chunk_id,
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


@lru_cache
def _load_section_rules(path: Path = RULES_PATH) -> tuple[SectionType, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    default_type = SectionType(raw.get("default_section_type", SectionType.OTHER))
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


def _classify_section(headings: Sequence[str | None]) -> SectionType:
    default_type, rules = _load_section_rules()
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


def _build_breadcrumbs(
    headings: Sequence[str | None],
    separator: str = " > ",
) -> str:
    return separator.join(title for title in headings if title)


def _parse_markdown(text: str) -> list[MarkdownSection]:
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


def _split_long_section(
    body: str,
    section_type: SectionType = SectionType.OTHER,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[str]:
    if section_type == SectionType.FAQ or len(body) <= max_chars:
        return [body]

    blocks = [part.strip() for part in re.split(r"\n{2,}", body) if part.strip()]
    parts = []
    current = []
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


def chunk_document(
    document: KBDocument,
    max_chunk_chars: int = settings.rag.max_chunk_chars,
    chunk_overlap: int = settings.rag.chunk_overlap,
) -> list[Chunk]:
    sections = _parse_markdown(document.content)
    chunks: list[Chunk] = []
    chunk_index = 0

    for section in sections:
        breadcrumbs = _build_breadcrumbs(section.headings)
        section_type = _classify_section(section.headings)
        prefix = f"{breadcrumbs}\n\n" if breadcrumbs else ""
        max_body = max(max_chunk_chars - len(prefix), 200)

        parts = _split_long_section(
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
                section_path=breadcrumbs,
            )
            chunks.append(
                Chunk(
                    chunk_id=make_chunk_id(document.doc_id, chunk_index),
                    doc_id=document.doc_id,
                    filepath=document.filepath,
                    chunk_index=chunk_index,
                    content=f"{prefix}{part}",
                    metadata=metadata,
                )
            )
            chunk_index += 1

    return chunks
