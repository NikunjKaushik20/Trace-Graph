import time
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from tracegraph.api.state import AppState, get_state
from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.graph.connection import GraphTimer
from tracegraph.graph.queries.evidence import CANDIDATE_EVIDENCE, TRACE_SCORES
from tracegraph.llm.factory import spend_meter
from tracegraph.market.work import Capability
from tracegraph.trace.settings import TraceSettings

router = APIRouter(tags=["ops"])
State = Annotated[AppState, Depends(get_state)]


# Fails closed: 503 when FalkorDB is down or unplugged, so the UI shows that nobody can pay
@router.get("/health")
async def health(state: State) -> JSONResponse:
    reachable = await state.database.is_reachable()
    body = {
        "falkordb": "up" if reachable else "down",
        "unplugged": state.database.unplugged,
        "can_pay": reachable,
        "guard_mode": state.guard_mode,
        "llm_mode": state.settings.llm_mode,
        "scorer": state.settings.scorer,
    }
    return JSONResponse(body, status_code=200 if reachable else 503)


# What the paid LLM has cost so far, against the limit that switches it off
@router.get("/llm/spend")
async def spend(state: State) -> dict[str, Any]:
    report = await spend_meter(state.settings, state.database).report()
    return {**asdict(report), "limit_reached": report.limit_reached}


# FalkorDB's execution plan and timing for the scoring query, the one every decision runs
@router.get("/profile/trace-score")
async def profile_trace_score(
    state: State,
    buyer_id: Annotated[str, Query(pattern=r"^buyer-[1-5]$")] = "buyer-1",
    capability: Capability = "summarise",
) -> dict[str, Any]:
    session = state.observer(buyer_id=buyer_id)
    request = EvidenceRequest(
        session.graph_name, buyer_id, capability, time.time(), session.guard_rules
    )
    params = request.as_query_params()
    query = CANDIDATE_EVIDENCE
    if state.settings.scorer == "udf":
        query, params = TRACE_SCORES, {**params, "settings": asdict(TraceSettings())}
    timer = GraphTimer()
    await state.database.run(session.graph_name, query, params, timer)
    plan = await state.database.profile(session.graph_name, query, params)
    return {"query": query.name, "graph_ms": timer.total_ms, "plan": plan}
