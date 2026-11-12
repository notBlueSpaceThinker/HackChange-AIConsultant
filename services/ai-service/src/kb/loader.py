import zipfile
from pathlib import Path, PurePosixPath

from src.schemas.domain.chunk import KBDocument


def _build_document(relative_path_str: str, content: str) -> KBDocument:
    """Нормализует текст и собирает замороженную модель KBDocument."""
    normalized_content = content.replace("\r\n", "\n")
    clean_rel_path = relative_path_str.replace("\\", "/").strip("/")
    return KBDocument.from_file(
        filepath=clean_rel_path,
        content=normalized_content,
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

                for zip_path in sorted(source.rglob("*.zip")):
                    documents.extend(load_kb(zip_path))

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
