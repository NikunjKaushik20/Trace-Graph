from dataclasses import asdict, dataclass

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.jobs import OPEN_TASK
from tracegraph.market.work import Capability


@dataclass(frozen=True)
class PlannedJob:
    job_id: str
    capability: Capability
    input_text: str


@dataclass(frozen=True)
class TaskPlan:
    task_id: str
    buyer_id: str
    text: str
    jobs: list[PlannedJob]
    t: float


# Records a task a buyer received and the jobs it was split into
async def open_task(
    database: GraphDatabase, graph_name: str, plan: TaskPlan, timer: GraphTimer | None = None
) -> None:
    params = {
        "buyer_id": plan.buyer_id,
        "task_id": plan.task_id,
        "text": plan.text,
        "jobs": [asdict(job) for job in plan.jobs],
        "t": plan.t,
    }
    await database.run(graph_name, OPEN_TASK, params, timer)
