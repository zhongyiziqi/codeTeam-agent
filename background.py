from collections.abc import Callable

from fastapi import BackgroundTasks

from codeteam.agents.runner import run_agent_task
from codeteam.config import get_settings
from codeteam.database import SessionLocal
from codeteam.indexing.service import index_repository
from codeteam.sandbox import execute_approved_patch
from codeteam.tasks import execute_patch_task, index_repository_task, run_agent_task_task


def index_repository_job(repository_id: str) -> None:
    with SessionLocal() as session:
        index_repository(session, repository_id)


def run_agent_task_job(task_id: str) -> None:
    with SessionLocal() as session:
        run_agent_task(session, task_id)


def execute_patch_job(execution_id: str) -> None:
    with SessionLocal() as session:
        execute_approved_patch(session, execution_id)


def dispatch_index(background_tasks: BackgroundTasks, repository_id: str) -> None:
    _dispatch(background_tasks, index_repository_job, index_repository_task.delay, repository_id)


def dispatch_agent(background_tasks: BackgroundTasks, task_id: str) -> None:
    _dispatch(background_tasks, run_agent_task_job, run_agent_task_task.delay, task_id)


def dispatch_patch(background_tasks: BackgroundTasks, execution_id: str) -> None:
    _dispatch(background_tasks, execute_patch_job, execute_patch_task.delay, execution_id)


def _dispatch(
    background_tasks: BackgroundTasks,
    local_job: Callable[[str], None],
    celery_job: Callable[[str], object],
    resource_id: str,
) -> None:
    mode = get_settings().task_dispatch_mode
    if mode == "celery":
        celery_job(resource_id)
        return
    if mode == "local":
        background_tasks.add_task(local_job, resource_id)
        return
    raise ValueError(f"Unsupported TASK_DISPATCH_MODE: {mode}")
