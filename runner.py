from sqlalchemy.orm import Session

from codeteam.agents.graph import build_agent_graph
from codeteam.models import AgentStep, AgentTask, PatchExecution, TaskStatus, utc_now


def run_agent_task(session: Session, task_id: str) -> dict:
    task = session.get(AgentTask, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    task.status = TaskStatus.running
    task.error_message = None
    session.commit()
    try:
        graph = build_agent_graph(session)
        state = {"repository_id": task.repository_id, "user_request": task.user_request}
        sequence = 1
        for update in graph.stream(state, stream_mode="updates"):
            agent_name, output_data = next(iter(update.items()))
            session.add(
                AgentStep(
                    task_id=task.id,
                    sequence=sequence,
                    agent_name=agent_name,
                    status=TaskStatus.completed,
                    input_data=None,
                    output_data=output_data,
                    completed_at=utc_now(),
                )
            )
            state.update(output_data)
            sequence += 1
            session.commit()
        task.final_report = state["final_report"]
        implementation = task.final_report.get("implementation", {})
        unified_diff = implementation.get("unified_diff")
        if unified_diff:
            task.patch_execution = PatchExecution(
                unified_diff=unified_diff,
                test_command=implementation.get("test_command", []),
            )
        task.status = TaskStatus.completed
        session.commit()
        return task.final_report
    except Exception as exc:
        session.rollback()
        task = session.get(AgentTask, task_id)
        if task is not None:
            task.status = TaskStatus.failed
            task.error_message = str(exc)
            session.commit()
        raise