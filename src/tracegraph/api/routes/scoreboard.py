import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent

from tracegraph.api.state import AppState, get_state
from tracegraph.eval.contract import Adversary, MarketContract
from tracegraph.eval.lanes import LANES, LANES_BY_NAME
from tracegraph.eval.market_run import MarketRun
from tracegraph.eval.outcomes import SeedResult
from tracegraph.graph.connection import GraphUnavailableError
from tracegraph.graph.queries.agent_eval import LATEST_AGENT_EVAL
from tracegraph.graph.queries.query import Query as GraphQuery
from tracegraph.graph.queries.scoreboard import LATEST_SCOREBOARD

router = APIRouter(tags=["scoreboard"])
State = Annotated[AppState, Depends(get_state)]
MAX_LIVE_LANES = 2
LaneName = Annotated[str, Query(pattern="^(" + "|".join(lane.name for lane in LANES) + ")$")]


# The latest 100-seed scoreboard, read from FalkorDB
@router.get("/scoreboard")
async def scoreboard(state: State) -> dict[str, Any]:
    graph = state.settings.scoreboard_graph
    return await latest(state, graph, LATEST_SCOREBOARD, "no scoreboard has been run yet")


# The latest agent eval: L1 per lane and the L2 tool-choice score
@router.get("/evals/agent")
async def agent_eval(state: State) -> dict[str, Any]:
    graph = state.settings.ops_graph
    return await latest(state, graph, LATEST_AGENT_EVAL, "no agent eval has been run yet")


# The newest saved run, or a 404 when the graph or the run is not there yet
async def latest(state: AppState, graph: str, query: GraphQuery, missing: str) -> dict[str, Any]:
    if graph not in await state.database.list_graphs():
        raise HTTPException(404, missing)
    rows = await state.database.rows(graph, query)
    if not rows:
        raise HTTPException(404, missing)
    return rows[0]


# Refuses a live lane before its stream opens when too many are already running
def free_live_slot(state: State) -> None:
    if state.live_lanes >= MAX_LIVE_LANES:
        raise HTTPException(429, f"{MAX_LIVE_LANES} live lanes are already running; try again soon")


# One lane on one seed, played live in FalkorDB, with the fraud counter after every round
@router.get(
    "/scoreboard/live",
    response_class=EventSourceResponse,
    dependencies=[Depends(free_live_slot)],
)
async def live_lane(
    state: State,
    lane: LaneName,
    adversary: Adversary = "strat",
    seed: Annotated[int, Query(ge=1000, le=1099)] = 1000,
) -> AsyncIterator[ServerSentEvent]:
    rounds: asyncio.Queue[SeedResult | None] = asyncio.Queue()

    # Hands each finished round to the stream
    async def on_round(result: SeedResult) -> None:
        await rounds.put(result)

    run = MarketRun(
        state.database,
        MarketContract(),
        LANES_BY_NAME[lane],
        adversary,
        seed,
        on_round=on_round,
        graph_tag=f"-live{uuid.uuid4().hex[:6]}",
    )
    state.live_lanes += 1
    playing = asyncio.create_task(run.play())
    playing.add_done_callback(lambda _: rounds.put_nowait(None))
    try:
        while (result := await rounds.get()) is not None:
            yield ServerSentEvent(event="round", data=round_update(result))
        final = await playing
        yield ServerSentEvent(event="end", data={**round_update(final), "jobs": final.jobs})
    except GraphUnavailableError as error:
        yield ServerSentEvent(event="error", data={"detail": f"FalkorDB is unavailable: {error}"})
    finally:
        playing.cancel()
        state.live_lanes -= 1


# The counter after one round
def round_update(result: SeedResult) -> dict[str, Any]:
    return {
        "lane": result.lane,
        "adversary": result.adversary,
        "seed": result.seed,
        "round": len(result.fraud_by_round),
        "fraud_sats": result.fraud_sats,
        "malicious_jobs": result.malicious_jobs,
        "quarantined_at_round": result.quarantined_at_round,
        "round_ms": result.round_ms[-1] if result.round_ms else 0.0,
    }
