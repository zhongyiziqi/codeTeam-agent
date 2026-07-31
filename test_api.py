from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from codeteam.database import get_db
from codeteam.main import app
from codeteam.models import AgentTask, ApprovalStatus, PatchExecution, Repository


def test_health_and_repository_creation(session: Session, sample_repository: Path):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            created = client.post(
                "/api/v1/repositories",
                json={"name": "sample", "local_path": str(sample_repository)},
            )
            listed = client.get("/api/v1/repositories")
    finally:
        app.dependency_overrides.clear()

    assert health.status_code == 200
    assert created.status_code == 201
    assert created.json()["name"] == "sample"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_patch_can_be_rejected(session: Session, sample_repository: Path):
    repository = Repository(name="sample", local_path=str(sample_repository))
    task = AgentTask(repository=repository, user_request="Change authentication")
    execution = PatchExecution(
        task=task,
        unified_diff="--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-old\n+new\n",
    )
    session.add(execution)
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/tasks/{task.id}/approval", json={"approved": False})
    finally:
        app.dependency_overrides.clear()

    session.refresh(execution)
    assert response.status_code == 200
    assert execution.status == ApprovalStatus.rejected