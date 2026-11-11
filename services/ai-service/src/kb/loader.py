import zipfile
from pathlib import Path, PurePosixPath

from src.schemas.domain.chunk import KBDocument


def _extract_title(content: str, fallback: str) -> str:
    """Извлекает заголовок первого уровня (# ...) из текста документа."""
    for line in content.split("\n"):
        cleaned = line.strip()
        if cleaned.startswith("#"):
            title = cleaned.lstrip("#").strip()
            if title:
                return title
    return fallback


def _build_document(relative_path_str: str, content: str) -> KBDocument:
    """Нормализует текст и собирает замороженную модель KBDocument."""
    normalized_content = content.replace("\r\n", "\n")
    clean_rel_path = relative_path_str.replace("\\", "/").strip("/")
    parts = clean_rel_path.split("/")

    category = parts[0] if len(parts) > 1 else ""
    filename = parts[-1]
    title = _extract_title(normalized_content, fallback=filename)

    # Поле product_name заполняется только для продуктовых файлов (20-products/*)
    product_name = title if category == "20-products" else None

    return KBDocument.from_file(
        source_file=clean_rel_path,
        title=title,
        content=normalized_content,
        product_name=product_name,
    )


def load_kb(source: Path) -> list[KBDocument]:
    """
    Загружает все .md файлы из распакованной директории или ZIP-архива.
    Возвращает детерминированный список KBDocument.
    """
    if not source.exists():
        raise FileNotFoundError(f"Источник базы знаний не найден: {source}")

    documents: list[KBDocument] = []

    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source, "r") as archive:
            for file_info in sorted(archive.infolist(), key=lambda x: x.filename):
                raw_name = file_info.filename
                if (
                    "__MACOSX" in raw_name
                    or file_info.is_dir()
                    or not raw_name.lower().endswith(".md")
                ):
                    continue

                posix_path = PurePosixPath(raw_name)
                if len(posix_path.parts) > 2:
                    rel_path = "/".join(posix_path.parts[-2:])
                else:
                    rel_path = posix_path.as_posix()

                with archive.open(file_info, "r") as f:
                    content = f.read().decode("utf-8-sig")

                documents.append(_build_document(rel_path, content))

    elif source.is_dir():
        for file_path in sorted(source.rglob("*.md")):
            try:
                rel_path = file_path.relative_to(source).as_posix()
            except ValueError:
                rel_path = file_path.name

            content = file_path.read_text(encoding="utf-8-sig")
            documents.append(_build_document(rel_path, content))

    else:
        raise ValueError(f"Неподдерживаемый тип источника базы знаний: {source}")

    return documents
