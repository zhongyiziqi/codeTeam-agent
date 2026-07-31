from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from codeteam.agents.runner import run_agent_task
from codeteam.indexing.service import index_repository
from codeteam.models import AgentStep, AgentTask, Repository, TaskStatus


def test_agent_workflow_produces_evidence_backed_report(
    session: Session, sample_repository: Path
):
    repository = Repository(name="sample", local_path=str(sample_repository))
    session.add(repository)
    session.commit()
    index_repository(session, repository.id)
    task = AgentTask(
        repository_id=repository.id,
        user_request="Explain token authentication and suggest tests for invalid tokens",
    )
    session.add(task)
    session.commit()

    report = run_agent_task(session, task.id)

    steps = list(
        session.scalars(
            select(AgentStep).where(AgentStep.task_id == task.id).order_by(AgentStep.sequence)
        ).all()
    )
    session.refresh(task)
    assert task.status == TaskStatus.completed
    assert [step.agent_name for step in steps] == [
        "planner",
        "retriever",
        "analyst",
        "developer",
        "reviewer",
        "reporter",
    ]
    assert report["evidence"]
    assert any(item["file_path"] == "auth.py" for item in report["evidence"])
    assert report["review"]["tests"]
