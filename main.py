from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from codeteam.api.repos import router as repositories_router
from codeteam.api.tasks import router as tasks_router
from codeteam.config import get_settings
from codeteam.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding_hnsw "
                    "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
    get_settings().repository_root.mkdir(parents=True, exist_ok=True)
    get_settings().sandbox_root.mkdir(parents=True, exist_ok=True)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(repositories_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}