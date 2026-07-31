from pydantic import BaseModel, Field


class PlanOutput(BaseModel):
    task_type: str
    summary: str
    search_queries: list[str] = Field(min_length=1, max_length=6)
    investigation_steps: list[str]


class AnalysisOutput(BaseModel):
    findings: list[str]
    call_flow: list[str]
    evidence_refs: list[str]
    uncertainties: list[str]


class ImplementationOutput(BaseModel):
    approach: str
    file_changes: list[str]
    constraints: list[str]
    unified_diff: str | None = None
    test_command: list[str] = Field(default_factory=list)


class ReviewOutput(BaseModel):
    risks: list[str]
    edge_cases: list[str]
    tests: list[str]
    verdict: str
