import argparse
import asyncio
from pathlib import Path

from qdrant_client import models

from src.config import DATA_DIR, settings
from src.core.embeddings import embed_texts
from src.core.qdrant import (
    DENSE_VECTOR_NAME,
    SPARSE_MODEL_NAME,
    SPARSE_VECTOR_NAME,
    close_qdrant_client,
    create_collection_if_not_exists,
    get_async_qdrant_client,
)
from src.kb.loader import load_kb
from src.rag.chunker import chunk_document

BATCH_SIZE = 64


async def ingest(data_dir: Path, recreate: bool) -> None:
    client = get_async_qdrant_client()
    docs = load_kb(DATA_DIR)
    chunks = [chunk for doc in docs for chunk in chunk_document(doc)]

    try:
        if recreate and await client.collection_exists(settings.qdrant.collection_name):
            await client.delete_collection(settings.qdrant.collection_name)
        await create_collection_if_not_exists()
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            vectors = await embed_texts([chunk.content for chunk in batch])
            await client.upsert(
                collection_name=settings.qdrant.collection_name,
                points=[
                    models.PointStruct(
                        id=str(chunk.chunk_id),
                        vector={
                            DENSE_VECTOR_NAME: vector,
                            SPARSE_VECTOR_NAME: models.Document(
                                text=chunk.content, model=SPARSE_MODEL_NAME
                            ),
                        },
                        payload=chunk.model_dump(mode="json"),
                    )
                    for chunk, vector in zip(batch, vectors, strict=True)
                ],
                wait=True,
            )
    finally:
        await close_qdrant_client()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    if not args.data_dir.exists():
        raise ValueError("Data directory does not exist")
    asyncio.run(ingest(args.data_dir, recreate=args.recreate))


if __name__ == "__main__":
    main()
