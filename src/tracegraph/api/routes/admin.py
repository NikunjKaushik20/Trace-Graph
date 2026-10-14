import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from tracegraph.api.schemas import GuardRequest, PlugRequest, SeedRequest
from tracegraph.api.state import AppState, get_state
from tracegraph.eval.saved_results import restore_saved_results
from tracegraph.market.seed import add_ring, seed_demo_market

State = Annotated[AppState, Depends(get_state)]


# Lets a request through only with the admin token from the settings
def require_admin(
    state: State, admin_token: Annotated[str | None, Header(max_length=200)] = None
) -> None:
    expected = state.settings.admin_token
    if not expected:
        raise HTTPException(403, "admin routes are off: set ADMIN_TOKEN to turn them on")
    if admin_token is None or not secrets.compare_digest(admin_token, expected):
        raise HTTPException(403, "wrong admin token")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# Rebuilds the demo market, with or without the ring, and stores kept eval results again
@router.post("/seed")
async def seed(request: SeedRequest, state: State) -> dict[str, Any]:
    settings = state.settings
    spec = await seed_demo_market(
        state.database,
        settings.shared_graph,
        settings.embedding_dimensions,
        time.time(),
        with_ring=request.with_ring,
        with_udf=settings.scorer == "udf",
    )
    await restore_saved_results(state.database, settings)
    return {"providers": len(spec.providers), "buyers": len(spec.buyers), "jobs": len(spec.history)}


# The demo's "too good to be true" moment: the ring and its fake reviews arrive
@router.post("/ring")
async def ring_arrives(state: State) -> dict[str, Any]:
    settings = state.settings
    spec = await add_ring(
        state.database, settings.shared_graph, settings.embedding_dimensions, time.time()
    )
    return {
        "providers": [listing.id for listing in spec.providers],
        "fake_reviews": len(spec.history),
    }


# The Poison and Guard buttons: which writes count from now on
@router.post("/guard")
async def set_guard(request: GuardRequest, state: State) -> dict[str, str]:
    state.guard_mode = request.mode
    return {"guard_mode": state.guard_mode}


# Pull the plug: every tool now finds FalkorDB unreachable, so no buyer can score or pay
@router.post("/plug")
async def set_plug(request: PlugRequest, state: State) -> dict[str, bool]:
    state.database.unplugged = not request.connected
    return {"connected": request.connected}
