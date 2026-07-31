from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from codeteam.api.background import dispatch_index
from codeteam.config import get_settings
from codeteam.database import DbSession
from codeteam.models import Repository
from codeteam.schemas import RepositoryCreate, RepositoryRead

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED)
def create_repository(payload: RepositoryCreate, session: DbSession):
    if not payload.source_url and not payload.local_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_url or local_path is required",
        )
    repository = Repository(
        name=payload.name,
        source_url=payload.source_url,
        local_path=payload.local_path or "",
        branch=payload.branch,
    )
    session.add(repository)
    session.flush()
    if payload.source_url and not payload.local_path:
        repository.local_path = str(
            (get_settings().repository_root / repository.id).resolve()
        )
    session.commit()
    session.refresh(repository)
    return repository


@router.get("", response_model=list[RepositoryRead])
def list_repositories(session: DbSession):
    return list(session.scalars(select(Repository).order_by(Repository.created_at.desc())).all())


@router.get("/{repository_id}", response_model=RepositoryRead)
def get_repository(repository_id: str, session: DbSession):
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repository


@router.post("/{repository_id}/index", response_model=RepositoryRead)
def start_indexing(
    repository_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
):
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if not repository.source_url and not Path(repository.local_path).exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Local repository path does not exist",
        )
    dispatch_index(background_tasks, repository.id)
    return repository
