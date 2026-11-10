from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.chat import router
from src.config import settings

app = FastAPI(title="Energytool AI service", version="0.1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "mock": settings.is_mock}