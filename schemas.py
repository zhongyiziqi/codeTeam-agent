from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from codeteam.models import ApprovalStatus, RepositoryStatus, TaskStatus


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_url: str | None = None
    local_path: str | None = None
    branch: str | None = None


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_url: str | None
    local_path: str
    branch: str | None
    commit_hash: str | None
    status: RepositoryStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    repository_id: str
    user_request: str = Field(min_length=3, max_length=10000)


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    agent_name: str
    status: TaskStatus
    input_data: dict | None
    output_data: dict | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class PatchApproval(BaseModel):
    approved: bool


class PatchExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: ApprovalStatus
    unified_diff: str
    test_command: list[str]
    sandbox_path: str | None
    apply_output: str | None
    test_output: str | None
    exit_code: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    user_request: str
    status: TaskStatus
    final_report: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStepRead] = Field(default_factory=list)
    patch_execution: PatchExecutionRead | None = None


class HealthRead(BaseModel):
    status: str
    environment: str
