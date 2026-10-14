import re
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from tracegraph.agent.loop import BuyerAgent
from tracegraph.agent.runs import TaskRun
from tracegraph.api.schemas import TaskRequest, TaskStarted
from tracegraph.api.state import AppState, get_state
from tracegraph.api.task_runs import TaskHandle
from tracegraph.graph.queries.jobs import TASK_IDS

router = APIRouter(tags=["tasks"])
State = Annotated[AppState, Depends(get_state)]
TASK_NUMBER = re.compile(r"^task-(\d+)$")


# A task this server started, or a 404 before any stream opens
def require_task(task_id: str, state: State) -> TaskHandle:
    handle = state.tasks.get(task_id)
    if handle is None:
        raise HTTPException(404, f"no task {task_id} on this server")
    return handle


Handle = Annotated[TaskHandle, Depends(require_task)]


# Gives a buyer agent a task; it runs in the background and its steps stream from events_url
@router.post("/tasks", status_code=202)
async def start_task(request: TaskRequest, state: State) -> TaskStarted:
    session = state.buyer_session(request.buyer_id, request.view)
    taken = await taken_task_ids(state, session.graph_name)
    task_id = request.task_id or next_task_id(taken)
    if task_id in taken:
        raise HTTPException(409, f"task {task_id} already exists")
    model = state.models.model_for(request.buyer_id)

    # The agent's run, reporting every step to the task's followers
    async def work(handle: TaskHandle) -> TaskRun:
        agent = BuyerAgent(session, model, events=handle.publish)
        return await agent.run_task(task_id, request.text)

    state.tasks.start(TaskHandle(task_id, request.buyer_id, request.text), work)
    return TaskStarted(
        task_id=task_id, buyer_id=request.buyer_id, events_url=f"/tasks/{task_id}/events"
    )


# Where a task stands: running, done or failed, and each job's tool path and narration
@router.get("/tasks/{task_id}")
async def task_status(task_id: str, handle: Handle) -> dict[str, Any]:
    jobs = [] if handle.run is None else [job_summary(job) for job in handle.run.jobs]
    return {
        "task_id": handle.task_id,
        "buyer_id": handle.buyer_id,
        "status": handle.status,
        "error": handle.error,
        "events": len(handle.events),
        "jobs": jobs,
    }


# The task's events as server-sent events: everything so far, then live until it ends
@router.get("/tasks/{task_id}/events", response_class=EventSourceResponse)
async def task_events(handle: Handle) -> AsyncIterator[ServerSentEvent]:
    async for index, event in handle.follow():
        yield ServerSentEvent(event=event.kind, id=str(index), data=asdict(event))
    yield ServerSentEvent(event="end", data={"status": handle.status, "error": handle.error})


# One job's result for the status endpoint
def job_summary(job: Any) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "capability": job.capability,
        "tool_path": job.tool_path,
        "narration": job.narration,
        "citations": asdict(job.citations),
        "hit_step_cap": job.hit_step_cap,
        "settled_by_safety_net": job.settled_by_safety_net,
    }


# Task ids already used, in the graph or by a task this server is still running
async def taken_task_ids(state: AppState, graph_name: str) -> set[str]:
    rows = await state.database.rows(graph_name, TASK_IDS)
    return {str(row["task_id"]) for row in rows} | set(state.tasks.handles)


# The next task-N after the highest number already taken
def next_task_id(taken: set[str]) -> str:
    numbers = [int(match.group(1)) for task_id in taken if (match := TASK_NUMBER.match(task_id))]
    return f"task-{max(numbers, default=0) + 1}"
