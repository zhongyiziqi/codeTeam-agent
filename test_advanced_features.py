from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from codeteam.agents.graph import _route_after_analysis, _route_after_review
from codeteam.config import Settings
from codeteam.indexing.embeddings import HashEmbeddings, create_embeddings
from codeteam.models import AgentTask, ApprovalStatus, CodeChunk, PatchExecution, Repository
from codeteam.sandbox import _validate_diff_paths, execute_approved_patch


def test_embedding_provider_requires_openai_key():
    settings = Settings(embedding_provider="openai", openai_api_key=None)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_embeddings(settings)

    assert len(HashEmbeddings(32).embed_query("authentication token")) == 32


def test_postgres_schema_uses_native_vector():
    ddl = str(CreateTable(CodeChunk.__table__).compile(dialect=postgresql.dialect()))
    assert "VECTOR(1536)" in ddl
    distance = CodeChunk.embedding.op("<=>")([0.0] * 1536)
    query = str(select(CodeChunk).order_by(distance).compile(dialect=postgresql.dialect()))
    assert "<=>" in query


def test_agent_routes_are_bounded():
    assert _route_after_analysis({"retrieved_context": [], "retrieval_attempts": 0}) == "retry"
    assert (
        _route_after_analysis({"retrieved_context": [], "retrieval_attempts": 2}) == "continue"
    )
    assert (
        _route_after_review({"review": {"verdict": "needs_revision"}, "revision_attempts": 0})
        == "revise"
    )
    assert (
        _route_after_review({"review": {"verdict": "needs_revision"}, "revision_attempts": 2})
        == "finish"
    )


def test_patch_execution_requires_approval(session: Session, sample_repository: Path):
    execution = _create_execution(session, sample_repository, ApprovalStatus.awaiting_approval)

    with pytest.raises(ValueError, match="approved"):
        execute_approved_patch(session, execution.id)


def test_approved_patch_runs_in_copied_workspace(
    session: Session, sample_repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path / "sandboxes"))
    from codeteam.config import get_settings

    get_settings.cache_clear()
    execution = _create_execution(session, sample_repository, ApprovalStatus.approved)

    result = execute_approved_patch(session, execution.id)

    session.refresh(execution)
    assert result["status"] == ApprovalStatus.succeeded
    assert execution.exit_code == 0
    assert "CodeTeam validated" in (Path(execution.sandbox_path) / "auth.py").read_text()
    assert "CodeTeam validated" not in (sample_repository / "auth.py").read_text()
    get_settings.cache_clear()


def test_patch_rejects_parent_traversal():
    malicious = "--- a/../outside.py\n+++ b/../outside.py\n@@ -1 +1 @@\n-old\n+new\n"
    with pytest.raises(ValueError, match="Unsafe patch path"):
        _validate_diff_paths(malicious)


def _create_execution(
    session: Session, repository_path: Path, status: ApprovalStatus
) -> PatchExecution:
    repository = Repository(name="sandbox", local_path=str(repository_path))
    task = AgentTask(repository=repository, user_request="Add a docstring")
    diff = (
        "diff --git a/auth.py b/auth.py\n"
        "--- a/auth.py\n"
        "+++ b/auth.py\n"
        "@@ -1,4 +1,5 @@\n"
        " class TokenService:\n"
        "+    # CodeTeam validated\n"
        "     def validate_token(self, token: str) -> bool:\n"
        "         return token == 'valid-token'\n"
        " \n"
    )
    execution = PatchExecution(
        task=task,
        status=status,
        unified_diff=diff,
        test_command=["pytest", "-q"],
    )
    session.add(execution)
    session.commit()
    return execution