from pathlib import Path

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from codeteam.models import CodeChunk, Repository
from codeteam.rag.retriever import HybridCodeRetriever


def create_repository_tools(session: Session, repository_id: str) -> list[BaseTool]:
    @tool
    def search_code(query: str, limit: int = 8) -> list[dict]:
        """Search repository code using hybrid semantic and keyword retrieval."""
        return [
            result.to_dict()
            for result in HybridCodeRetriever(session).search(repository_id, query, limit=limit)
        ]

    @tool
    def read_file_chunk(chunk_id: str) -> dict:
        """Read an indexed source chunk by its identifier."""
        chunk = session.get(CodeChunk, chunk_id)
        if chunk is None or chunk.repository_id != repository_id:
            raise ValueError("Chunk not found in this repository")
        return {
            "file_path": chunk.file_path,
            "symbol_name": chunk.symbol_name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
        }

    @tool
    def list_repo_tree() -> list[str]:
        """List indexed file paths in the repository."""
        statement = (
            select(CodeChunk.file_path)
            .where(CodeChunk.repository_id == repository_id)
            .distinct()
            .order_by(CodeChunk.file_path)
        )
        return list(session.scalars(statement).all())

    return [search_code, read_file_chunk, list_repo_tree]


def repository_path(session: Session, repository_id: str) -> Path:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise ValueError("Repository not found")
    return Path(repository.local_path)
