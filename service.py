from sqlalchemy import delete
from sqlalchemy.orm import Session

from codeteam.indexing.code_splitter import split_source_file
from codeteam.indexing.embeddings import create_embeddings
from codeteam.indexing.repo_loader import (
    iter_source_files,
    prepare_repository,
    repository_revision,
)
from codeteam.models import CodeChunk, Repository, RepositoryStatus


def index_repository(session: Session, repository_id: str) -> int:
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise ValueError(f"Repository not found: {repository_id}")

    repository.status = RepositoryStatus.indexing
    repository.error_message = None
    session.commit()

    try:
        root = prepare_repository(repository.source_url, repository.local_path, repository.branch)
        branch, commit_hash = repository_revision(root)
        repository.branch = branch or repository.branch
        repository.commit_hash = commit_hash
        session.execute(delete(CodeChunk).where(CodeChunk.repository_id == repository.id))

        chunk_data = [
            chunk
            for source_file in iter_source_files(root)
            for chunk in split_source_file(source_file)
        ]
        embeddings = create_embeddings().embed_documents([chunk.content for chunk in chunk_data])
        for chunk, embedding in zip(chunk_data, embeddings, strict=True):
            session.add(
                CodeChunk(
                    repository_id=repository.id,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    symbol_name=chunk.symbol_name,
                    chunk_type=chunk.chunk_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    embedding=embedding,
                )
            )
        repository.status = RepositoryStatus.ready
        session.commit()
        return len(chunk_data)
    except Exception as exc:
        session.rollback()
        repository = session.get(Repository, repository_id)
        if repository is not None:
            repository.status = RepositoryStatus.failed
            repository.error_message = str(exc)
            session.commit()
        raise
