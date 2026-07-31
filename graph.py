import json
from collections.abc import Callable

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from sqlalchemy.orm import Session

from codeteam.agents.outputs import (
    AnalysisOutput,
    ImplementationOutput,
    PlanOutput,
    ReviewOutput,
)
from codeteam.agents.prompts import (
    ANALYST_PROMPT,
    DEVELOPER_PROMPT,
    PLANNER_PROMPT,
    REVIEWER_PROMPT,
)
from codeteam.agents.state import AgentState
from codeteam.config import get_settings
from codeteam.rag.retriever import HybridCodeRetriever


def build_agent_graph(session: Session):
    graph = StateGraph(AgentState)
    graph.add_node("planner", _planner_node)
    graph.add_node("retriever", _retriever_node(session))
    graph.add_node("analyst", _analyst_node)
    graph.add_node("developer", _developer_node)
    graph.add_node("reviewer", _reviewer_node)
    graph.add_node("reporter", _reporter_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "analyst")
    graph.add_conditional_edges(
        "analyst", _route_after_analysis, {"retry": "retriever", "continue": "developer"}
    )
    graph.add_edge("developer", "reviewer")
    graph.add_conditional_edges(
        "reviewer", _route_after_review, {"revise": "developer", "finish": "reporter"}
    )
    graph.add_edge("reporter", END)
    return graph.compile()


def _planner_node(state: AgentState) -> dict:
    request = state["user_request"]
    fallback = PlanOutput(
        task_type="repository_analysis",
        summary=request,
        search_queries=[request, f"implementation related to {request}", f"tests for {request}"],
        investigation_steps=[
            "Locate relevant implementations and entry points",
            "Trace dependencies and existing tests",
            "Propose the smallest evidence-backed change",
        ],
    )
    output = _structured_output(PlanOutput, PLANNER_PROMPT, request, fallback)
    return {"plan": output.model_dump()}


def _retriever_node(session: Session) -> Callable[[AgentState], dict]:
    def retrieve(state: AgentState) -> dict:
        retriever = HybridCodeRetriever(session)
        unique_results: dict[str, dict] = {}
        queries = list(state["plan"]["search_queries"])
        if state.get("analysis", {}).get("uncertainties"):
            queries.extend(state["analysis"]["uncertainties"])
        for query in queries:
            for result in retriever.search(state["repository_id"], query, limit=5):
                existing = unique_results.get(result.chunk_id)
                if existing is None or result.score > existing["score"]:
                    unique_results[result.chunk_id] = result.to_dict()
        ranked = sorted(unique_results.values(), key=lambda item: item["score"], reverse=True)
        return {
            "retrieved_context": ranked[:12],
            "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
        }

    return retrieve


def _analyst_node(state: AgentState) -> dict:
    context = state.get("retrieved_context", [])
    refs = [
        f"{item['file_path']}:{item['start_line']}-{item['end_line']}"
        for item in context
    ]
    fallback = AnalysisOutput(
        findings=[
            f"Retrieved {len(context)} evidence chunks for the requested change.",
            *[
                (
                    f"{item['file_path']} contains "
                    f"{item.get('symbol_name') or 'relevant file content'}."
                )
                for item in context[:5]
            ],
        ],
        call_flow=refs[:5],
        evidence_refs=refs,
        uncertainties=[] if context else ["No indexed evidence matched the request."],
    )
    payload = json.dumps(
        {"request": state["user_request"], "evidence": context}, ensure_ascii=False
    )
    output = _structured_output(AnalysisOutput, ANALYST_PROMPT, payload, fallback)
    return {"analysis": output.model_dump()}


def _developer_node(state: AgentState) -> dict:
    evidence_paths = list(
        dict.fromkeys(item["file_path"] for item in state.get("retrieved_context", []))
    )
    fallback = ImplementationOutput(
        approach="Make the smallest change consistent with the retrieved implementation patterns.",
        file_changes=[f"Review and update {path}" for path in evidence_paths[:5]],
        constraints=[
            "Preserve existing public APIs unless the request requires a contract change.",
            "Do not implement behavior that is unsupported by repository evidence.",
        ],
        unified_diff=None,
        test_command=[],
    )
    payload = json.dumps(
        {
            "request": state["user_request"],
            "plan": state["plan"],
            "analysis": state["analysis"],
            "review_feedback": state.get("review"),
        },
        ensure_ascii=False,
    )
    output = _structured_output(ImplementationOutput, DEVELOPER_PROMPT, payload, fallback)
    return {"implementation": output.model_dump()}


def _reviewer_node(state: AgentState) -> dict:
    fallback = ReviewOutput(
        risks=["The proposal must be validated against the full call path before editing."],
        edge_cases=["Empty or malformed input", "Existing behavior and backwards compatibility"],
        tests=[
            "Add a focused test for the requested behavior.",
            "Run existing tests that cover the referenced files.",
        ],
        verdict="ready_for_human_review",
    )
    payload = json.dumps(
        {
            "request": state["user_request"],
            "evidence": state["analysis"],
            "proposal": state["implementation"],
        },
        ensure_ascii=False,
    )
    output = _structured_output(ReviewOutput, REVIEWER_PROMPT, payload, fallback)
    revision_attempts = state.get("revision_attempts", 0)
    if output.verdict == "needs_revision":
        revision_attempts += 1
    return {"review": output.model_dump(), "revision_attempts": revision_attempts}


def _route_after_analysis(state: AgentState) -> str:
    settings = get_settings()
    if not state.get("retrieved_context") and state.get("retrieval_attempts", 0) < (
        settings.agent_max_retrieval_attempts
    ):
        return "retry"
    return "continue"


def _route_after_review(state: AgentState) -> str:
    settings = get_settings()
    needs_revision = state.get("review", {}).get("verdict") == "needs_revision"
    if needs_revision and state.get("revision_attempts", 0) < settings.agent_max_revision_attempts:
        return "revise"
    return "finish"


def _reporter_node(state: AgentState) -> dict:
    return {
        "final_report": {
            "request": state["user_request"],
            "plan": state["plan"],
            "evidence": state.get("retrieved_context", []),
            "analysis": state["analysis"],
            "implementation": state["implementation"],
            "review": state["review"],
        }
    }


def _structured_output(
    schema: type[BaseModel], system_prompt: str, payload: str, fallback: BaseModel
) -> BaseModel:
    settings = get_settings()
    if settings.llm_provider != "openai" or not settings.openai_api_key:
        return fallback
    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(schema)
    return model.invoke(
        [("system", system_prompt), ("human", payload)],
    )
