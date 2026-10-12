from dataclasses import asdict
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.queries.views import FUNDING_CHAIN, JOB_STORY, NEIGHBOURHOOD, RECENT_JOBS
from tracegraph.investigation.quarantine import active_policies


# One job from task to outcome: decisions, provider, payment and the judge's reason
async def job_story(session: AgentSession, job_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    rows = await session.database.rows(session.graph_name, JOB_STORY, {"job_id": job_id}, timer)
    if not rows:
        raise ToolRefusedError(f"there is no job {job_id}")
    return {**rows[0], "graph_ms": timer.total_ms}


# The newest jobs and how they ended, optionally only the released or the refunded ones
async def recent_jobs(
    session: AgentSession, payment_status: str | None = None, limit: int = 20
) -> dict[str, Any]:
    timer = GraphTimer()
    params = {"payment_status": payment_status, "limit": min(max(limit, 1), 50)}
    rows = await session.database.rows(session.graph_name, RECENT_JOBS, params, timer)
    return {"jobs": rows, "graph_ms": timer.total_ms}


# Who funds a node, up to three hops, and who else those funders pay for
async def funding_chain(session: AgentSession, node_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    rows = await session.database.rows(
        session.graph_name, FUNDING_CHAIN, {"node_id": node_id}, timer
    )
    if not rows:
        raise ToolRefusedError(f"there is no node {node_id}")
    return {**rows[0], "graph_ms": timer.total_ms}


# Nodes and edges within one or two hops of a node
async def neighbourhood(
    session: AgentSession, node_id: str, hops: int = 1, limit: int = 200
) -> dict[str, Any]:
    timer = GraphTimer()
    params = {"node_id": node_id, "hops": min(max(hops, 1), 2), "limit": limit}
    rows = await session.database.rows(session.graph_name, NEIGHBOURHOOD, params, timer)
    if not rows:
        raise ToolRefusedError(f"there is no node {node_id}")
    return {**rows[0], "graph_ms": timer.total_ms}


# Every quarantine in force, optionally only the ones covering one provider
async def quarantines(session: AgentSession, provider_id: str | None = None) -> dict[str, Any]:
    timer = GraphTimer()
    policies = await active_policies(session.database, session.graph_name, timer)
    if provider_id is not None:
        policies = [policy for policy in policies if provider_id in policy.covered]
    return {"policies": [asdict(policy) for policy in policies], "graph_ms": timer.total_ms}
