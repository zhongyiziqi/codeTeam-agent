from typing import TypedDict


class AgentState(TypedDict, total=False):
    repository_id: str
    user_request: str
    plan: dict
    retrieved_context: list[dict]
    analysis: dict
    implementation: dict
    review: dict
    retrieval_attempts: int
    revision_attempts: int
    final_report: dict
