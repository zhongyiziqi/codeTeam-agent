from pathlib import Path

from sqlalchemy.orm import Session

from codeteam.indexing.service import index_repository
from codeteam.models import Repository, RepositoryStatus
from codeteam.rag.retriever import HybridCodeRetriever


def test_index_and_retrieve_authentication_code(session: Session, sample_repository: Path):
    repository = Repository(name="sample", local_path=str(sample_repository))
    session.add(repository)
    session.commit()

    chunk_count = index_repository(session, repository.id)
    results = HybridCodeRetriever(session).search(
        repository.id, "validate token authentication", limit=3
    )

    session.refresh(repository)
    assert repository.status == RepositoryStatus.ready
    assert chunk_count >= 3
    assert results
    assert any(result.file_path == "auth.py" for result in results)
    assert all(result.start_line <= result.end_line for result in results)
