from codeteam.agents.runner import run_agent_task
from codeteam.database import SessionLocal
from codeteam.indexing.service import index_repository
from codeteam.sandbox import execute_approved_patch
from codeteam.worker import celery_app


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    name="codeteam.index_repository",
)
def index_repository_task(self, repository_id: str) -> int:
    with SessionLocal() as session:
        return index_repository(session, repository_id)


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    name="codeteam.run_agent_task",
)
def run_agent_task_task(self, task_id: str) -> dict:
    with SessionLocal() as session:
        return run_agent_task(session, task_id)


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
    name="codeteam.execute_patch",
)
def execute_patch_task(self, execution_id: str) -> dict:
    with SessionLocal() as session:
        return execute_approved_patch(session, execution_id)
