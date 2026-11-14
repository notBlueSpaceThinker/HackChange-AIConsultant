import re

from src.kb.cleaner import clean_cell_text
from src.schemas.domain.chunk import KBDocument

_COL_SEP_PATTERN = re.compile(r"^\s*-{3,}(?:\s+-{3,})+\s*$")
_OUTER_BORDER_PATTERN = re.compile(r"^\s*-{10,}\s*$")


def _get_column_spans(separator_line: str) -> list[tuple[int, int]]:
    """
    Определяет координаты колонок (начало, конец) по строке из дефисов.
    """
    return [(m.start(), m.end()) for m in re.finditer(r"-{3,}", separator_line)]


def _parse_block_rows(
    lines: list[str],
    spans: list[tuple[int, int]],
    single_line_rows: bool = False,
) -> list[list[str]]:
    """
    Парсит блок строк таблицы по координатам колонок
    и склеивает многострочные ячейки.
    Если single_line_rows=True (таблица без верхней границы),
    каждая непустая строка считается отдельной записью.
    """
    rows: list[list[str]] = []
    current_row: list[str] = [""] * len(spans)

    for line in lines:
        if not line.strip():
            if any(current_row):
                rows.append([clean_cell_text(cell) for cell in current_row])
                current_row = [""] * len(spans)
            continue

        for idx, (start, end) in enumerate(spans):
            chunk = line[start:] if idx == len(spans) - 1 else line[start:end]
            cleaned = chunk.strip()
            if cleaned:
                current_row[idx] = f"{current_row[idx]} {cleaned}".strip()

        if single_line_rows and any(current_row):
            rows.append([clean_cell_text(cell) for cell in current_row])
            current_row = [""] * len(spans)

    if any(current_row):
        rows.append([clean_cell_text(cell) for cell in current_row])

    return rows


def _format_facts(headers: list[str], rows: list[list[str]]) -> list[str]:
    """
    Формирует самодостаточные предложения вида:
    «Параметр X: значение Y, условие Z: значение W.»
    """
    facts: list[str] = []
    for row in rows:
        parts: list[str] = []
        for idx, cell in enumerate(row):
            if not cell:
                continue

            header = headers[idx] if idx < len(headers) and headers[idx] else ""
            if header:
                if parts:
                    header_formatted = (
                        header[0].lower() + header[1:] if len(header) > 1 else header.lower()
                    )
                else:
                    header_formatted = header
                parts.append(f"{header_formatted}: {cell}")
            else:
                parts.append(cell)

        if parts:
            facts.append(", ".join(parts) + ".")

    return facts


def to_linearized_facts(text: str) -> str:
    """
    Находит Pandoc-таблицы в тексте и превращает каждую строку
    в самодостаточное текстовое предложение с сохранением шапки.
    """
    lines = text.split("\n")
    result_lines: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        is_top_border = bool(
            _OUTER_BORDER_PATTERN.match(lines[i]) or _COL_SEP_PATTERN.match(lines[i])
        )
        if is_top_border and i + 2 < n:
            header_lines: list[str] = []
            j = i + 1
            while j < n and not _COL_SEP_PATTERN.match(lines[j]):
                if not lines[j].strip() or _OUTER_BORDER_PATTERN.match(lines[j]):
                    break
                header_lines.append(lines[j])
                j += 1

            if j < n and _COL_SEP_PATTERN.match(lines[j]) and header_lines:
                spans = _get_column_spans(lines[j])
                body_lines: list[str] = []
                k = j + 1
                while k < n and not (
                    _OUTER_BORDER_PATTERN.match(lines[k]) or _COL_SEP_PATTERN.match(lines[k])
                ):
                    body_lines.append(lines[k])
                    k += 1

                if k < n and (
                    _OUTER_BORDER_PATTERN.match(lines[k]) or _COL_SEP_PATTERN.match(lines[k])
                ):
                    parsed_headers = _parse_block_rows(header_lines, spans)
                    headers = parsed_headers[0] if parsed_headers else []
                    body_rows = _parse_block_rows(body_lines, spans)

                    result_lines.extend(_format_facts(headers, body_rows))
                    i = k + 1
                    continue

        if i + 1 < n and _COL_SEP_PATTERN.match(lines[i + 1]) and lines[i].strip():
            spans = _get_column_spans(lines[i + 1])
            parsed_headers = _parse_block_rows([lines[i]], spans)
            headers = parsed_headers[0] if parsed_headers else []

            body_lines = []
            k = i + 2
            while k < n and lines[k].strip():
                body_lines.append(lines[k])
                k += 1

            body_rows = _parse_block_rows(body_lines, spans, single_line_rows=True)
            result_lines.extend(_format_facts(headers, body_rows))
            i = k
            continue

        result_lines.append(lines[i])
        i += 1

    return "\n".join(result_lines)


def linearize_documents(documents: list[KBDocument]) -> list[KBDocument]:
    """
    Применяет to_linearized_facts ко всем документам в списке (через model_copy).
    """
    return [
        doc.model_copy(update={"content": to_linearized_facts(doc.content)}) for doc in documents
    ]
