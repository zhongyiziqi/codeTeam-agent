import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from codeteam.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class RepositoryStatus(StrEnum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"


class TaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ApprovalStatus(StrEnum):
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    local_path: Mapped[str] = mapped_column(String(2048))
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[RepositoryStatus] = mapped_column(
        Enum(RepositoryStatus), default=RepositoryStatus.pending
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    chunks: Mapped[list["CodeChunk"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["AgentTask"]] = relationship(back_populates="repository")


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(2048), index=True)
    language: Mapped[str] = mapped_column(String(64))
    symbol_name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    chunk_type: Mapped[str] = mapped_column(String(64))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON().with_variant(VECTOR(1536), "postgresql"), nullable=True
    )

    repository: Mapped[Repository] = relationship(back_populates="chunks")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    user_request: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending)
    final_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    repository: Mapped[Repository] = relationship(back_populates="tasks")
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="AgentStep.sequence"
    )
    patch_execution: Mapped["PatchExecution | None"] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("agent_tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[AgentTask] = relationship(back_populates="steps")


class PatchExecution(Base):
    __tablename__ = "patch_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tasks.id"), unique=True, nullable=False, index=True
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.awaiting_approval
    )
    unified_diff: Mapped[str] = mapped_column(Text)
    test_command: Mapped[list[str]] = mapped_column(JSON, default=list)
    sandbox_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    apply_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    task: Mapped[AgentTask] = relationship(back_populates="patch_execution")
