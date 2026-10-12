import json
from dataclasses import dataclass
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.queries.catalogue import BUYER_JOB, DECISION_OWNER, PROVIDER_LISTING
from tracegraph.market.work import CAPABILITIES, Capability


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    task_id: str
    capability: Capability
    input_text: str
    status: str
    output: dict[str, Any] | None
    delivery_note: str
    price_sats: int | None
    provider_id: str | None
    decision_ids: list[str]

    # The newest decision made for this job, if any
    @property
    def latest_decision_id(self) -> str | None:
        return self.decision_ids[0] if self.decision_ids else None


# Loads one of this buyer's jobs, refusing ids that belong to someone else or do not exist
async def load_job(session: AgentSession, job_id: str, timer: GraphTimer) -> JobRecord:
    params = {"buyer_id": session.buyer_id, "job_id": job_id}
    rows = await session.database.rows(session.graph_name, BUYER_JOB, params, timer)
    if not rows:
        raise ToolRefusedError(f"{job_id} is not one of {session.buyer_id}'s jobs")
    row = rows[0]
    capability = row["capability"]
    if capability not in CAPABILITIES:
        raise ToolRefusedError(f"{job_id} asks for an unknown capability {capability!r}")
    output_json = row["output_json"]
    return JobRecord(
        job_id=job_id,
        task_id=str(row["task_id"]),
        capability=capability,
        input_text=str(row["input_text"]),
        status=str(row["status"]),
        output=json.loads(output_json) if output_json else None,
        delivery_note=str(row["delivery_note"] or ""),
        price_sats=row["price_sats"],
        provider_id=row["provider_id"],
        decision_ids=[str(decision_id) for decision_id in row["decision_ids"]],
    )


# Refuses to act on a decision this buyer did not make
async def require_own_decision(session: AgentSession, decision_id: str, timer: GraphTimer) -> None:
    rows = await session.database.rows(
        session.graph_name, DECISION_OWNER, {"decision_id": decision_id}, timer
    )
    if not rows:
        raise ToolRefusedError(f"there is no decision {decision_id}")
    if rows[0]["buyer_id"] != session.buyer_id:
        raise ToolRefusedError(f"{decision_id} was made by another buyer")


# A provider's name and listed price, refusing unknown providers
async def provider_listing(
    session: AgentSession, provider_id: str, timer: GraphTimer
) -> tuple[str, int]:
    rows = await session.database.rows(
        session.graph_name, PROVIDER_LISTING, {"provider_id": provider_id}, timer
    )
    if not rows:
        raise ToolRefusedError(f"there is no provider {provider_id}")
    return str(rows[0]["name"]), int(rows[0]["price_sats"])
