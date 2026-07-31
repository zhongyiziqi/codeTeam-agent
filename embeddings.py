import hashlib
import math
import re

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from codeteam.config import Settings, get_settings

TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]")


class HashEmbeddings(Embeddings):
    """Deterministic local embeddings for development and tests."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        return vector if magnitude == 0 else [value / magnitude for value in vector]


def create_embeddings(settings: Settings | None = None) -> Embeddings:
    settings = settings or get_settings()
    if settings.embedding_provider == "hash":
        return HashEmbeddings(settings.embedding_dimensions)
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            dimensions=settings.embedding_dimensions,
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
