import zipfile
from pathlib import Path, PurePosixPath
from typing import List
from src.schemas.domain.chunk import Document

def load_kb(source: Path) -> List[Document]:
    """
    Загружает базу знаний из ZIP-архива или распакованной директории.
    Скрывает разницу между источниками и возвращает единый список Document.
    
    :param source: Путь к директории БЗ или к файлу knowledge-base.zip
    :return: list[Document] для передачи в cleaner -> linearizer
    """
    documents: List[Document] = []

    if not source.exists():
        raise FileNotFoundError(f"Источник базы знаний не найден по пути: {source}")

    if source.is_file() and source.suffix.lower() == '.zip':
        with zipfile.ZipFile(source, 'r') as archive:
            for file_info in sorted(archive.infolist(), key=lambda x: x.filename):
                filename_str = file_info.filename
                
                if '__MACOSX' in filename_str or file_info.is_dir() or not filename_str.lower().endswith('.md'):
                    continue

                relative_path = PurePosixPath(filename_str)

                category = relative_path.parts[0] if relative_path.parts else "unknown"
                filename = relative_path.name

                with archive.open(file_info, 'r') as f:
                    content_bytes = f.read()
                content = content_bytes.decode('utf-8-sig')

                doc = _build_document(content, category, filename)
                documents.append(doc)

    elif source.is_dir():

        for file_path in sorted(source.rglob("*.md")):

            try:
                relative_path = file_path.relative_to(source)
            except ValueError:
                relative_path = file_path

            category = relative_path.parts[0] if relative_path.parts else "unknown"
            filename = file_path.name

            content = file_path.read_text(encoding='utf-8-sig')

            doc = _build_document(content, category, filename)
            documents.append(doc)
            
    else:
        raise ValueError(f"Неподдерживаемый тип источника базы знаний (ожидался ZIP или папка): {source}")

    return documents


def _build_document(content: str, category: str, filename: str) -> Document:
    """Вспомогательная функция для парсинга первой строки и нормализации текста."""
    normalized_content = content.replace('\r\n', '\n')

    lines = normalized_content.split('\n')
    product_name = "Без названия"
    
    if lines and lines[0].strip().startswith('#'):
        product_name = lines[0].strip().lstrip('#').strip()
    else:
        for line in lines:
            if line.strip().startswith('#'):
                product_name = line.strip().lstrip('#').strip()
                break

    return Document(
        page_content=normalized_content,
        metadata={
            "category": category,
            "filename": filename,
            "product_name": product_name
        }
    )


if __name__ == "__main__":
    import sys

    paths_to_check = [
        Path("knowledge-base.zip"),
        Path("knowledge-base"),
        Path("data/knowledge-base.zip"),
        Path("data/knowledge-base")
    ]
    
    target_path = None
    for p in paths_to_check:
        if p.exists():
            target_path = p
            if p.is_file():
                print(f"Найдено на диске: {p} (Режим тестирования ZIP)")
            else:
                print(f"Найдено на диске: папка {p}/ (Режим тестирования папки)")
            break
            
    if not target_path:
        print(f"Ошибка, не найдно ни knowledge-base.zip, ни папка knowledge-base")
        print("Текущая директория поиска:", Path(".").absolute())
        sys.exit(1)
        
    try:
        docs = load_kb(target_path)

        print(f" Всего извлечено документов: {len(docs)}")

        import json
        output_json = Path("parsed_kb.json")
        
        json_data = [doc.to_dict() for doc in docs]
        
        output_json.write_text(
            json.dumps(json_data, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )
        print(f"Данные успешно сохранены на диск в файл: {output_json.absolute()}")

    except Exception as e:
        print(f"\nТест упал с ошибкой:")
        import traceback
        traceback.print_exc()
