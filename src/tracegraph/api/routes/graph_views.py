from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from tracegraph.agent.session import ToolRefusedError
from tracegraph.agent.tools import explaining, views
from tracegraph.api.state import AppState, get_state
from tracegraph.evidence.rules import GuardMode
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.names import View
from tracegraph.graph.queries.views import GRAPH_SNAPSHOT

router = APIRouter(tags=["graph"])
State = Annotated[AppState, Depends(get_state)]
BuyerParam = Annotated[str, Query(pattern=r"^(buyer-[1-5]|observer)$")]
PaymentStatus = Literal["released", "refunded", "held"]


# Everything the graph view draws: nodes and edges of the shared market or a buyer's own graph
@router.get("/graph/snapshot")
async def snapshot(
    state: State, view: View = "together", buyer_id: BuyerParam = "observer"
) -> dict[str, Any]:
    if view == "alone" and buyer_id == "observer":
        raise HTTPException(422, "the alone view belongs to one buyer: pass buyer_id")
    session = state.observer(view, buyer_id)
    if session.graph_name not in await state.database.list_graphs():
        raise HTTPException(404, f"there is no graph {session.graph_name}: seed the demo first")
    timer = GraphTimer()
    rows = await state.database.rows(session.graph_name, GRAPH_SNAPSHOT, {"limit": 3000}, timer)
    row = rows[0] if rows else {"nodes": [], "edges": []}
    return {**row, "graph": session.graph_name, "graph_ms": timer.total_ms}


# The receipt for one decision
@router.get("/decisions/{decision_id}/receipt")
async def receipt(decision_id: str, state: State) -> dict[str, Any]:
    return await found(explaining.explain_decision(state.observer(), decision_id))


# The decision replayed as of its own time with another guard: would the pick change?
@router.get("/decisions/{decision_id}/what-if")
async def what_if(decision_id: str, state: State, guard: GuardMode = "unguarded") -> dict[str, Any]:
    return await found(explaining.what_if(state.observer(), decision_id, guard))


# Principal, buyer, task, job, decision and provider behind a payment
@router.get("/payments/{payment_id}/who-authorised")
async def payment_owner(payment_id: str, state: State) -> dict[str, Any]:
    return await found(explaining.who_authorised(state.observer(), payment_id))


# The newest jobs and how their payments ended, for the receipt list
@router.get("/jobs")
async def jobs(
    state: State,
    payment_status: PaymentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    return await views.recent_jobs(state.observer(), payment_status, limit)


# Every quarantine in force, with the decision that justified it
@router.get("/quarantines")
async def quarantines(state: State) -> dict[str, Any]:
    return await views.quarantines(state.observer())


# One job from task to outcome
@router.get("/jobs/{job_id}")
async def job(job_id: str, state: State) -> dict[str, Any]:
    return await found(views.job_story(state.observer(), job_id))


# The money behind a node
@router.get("/nodes/{node_id}/funding")
async def funding(node_id: str, state: State) -> dict[str, Any]:
    return await found(views.funding_chain(state.observer(), node_id))


# What a node is connected to, one or two hops out
@router.get("/nodes/{node_id}/neighbourhood")
async def around(
    node_id: str, state: State, hops: Annotated[int, Query(ge=1, le=2)] = 1
) -> dict[str, Any]:
    return await found(views.neighbourhood(state.observer(), node_id, hops))


# Awaits a lookup and turns "no such node" into a 404
async def found(lookup: Any) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await lookup
    except ToolRefusedError as error:
        raise HTTPException(404, str(error)) from error
    return result
