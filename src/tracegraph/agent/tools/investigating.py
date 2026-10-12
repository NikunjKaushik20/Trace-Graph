from dataclasses import asdict
from typing import Any

from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.agent.tools.lookups import require_own_decision
from tracegraph.graph.connection import GraphTimer
from tracegraph.investigation.case import InvestigationCase, QuarantineRefusedError


# Follows the money between a writer and a provider, and notes it on the decision
async def funding_path(
    session: AgentSession, decision_id: str, writer_id: str, provider_id: str
) -> dict[str, Any]:
    timer = GraphTimer()
    await require_own_decision(session, decision_id, timer)
    case = InvestigationCase(session.database, session.graph_name, decision_id, timer)
    path = await case.trace_funding(writer_id, provider_id)
    return {
        "writer_id": writer_id,
        "provider_id": provider_id,
        "found": path.found,
        "hops": path.hops,
        "path": path.node_ids,
        "shared_funders": path.shared_funders,
        "algorithm": "algo.SPpaths",
        "graph_ms": timer.total_ms,
    }


# Looks for a ring around a provider with WCC, CDLP, PageRank and betweenness
async def find_ring(session: AgentSession, decision_id: str, provider_id: str) -> dict[str, Any]:
    timer = GraphTimer()
    await require_own_decision(session, decision_id, timer)
    case = InvestigationCase(session.database, session.graph_name, decision_id, timer)
    report = await case.look_for_ring(provider_id)
    return {
        "provider_id": provider_id,
        "is_ring": report.is_ring,
        "ring_id": report.ring_id,
        "providers": report.providers,
        "writers": report.writers[:10],
        "writer_count": len(report.writers),
        "wallets": report.wallets,
        "hub_funder": report.hub_id,
        "bridge_wallet": report.bridge_id,
        "reports_from_outside_writers": report.outside_praise,
        "praise_community_size": len(report.praise_community),
        "algorithms": report.algorithms,
        "graph_ms": timer.total_ms,
    }


# Quarantines a ring for every buyer; needs find_ring and a funding path on the same decision
async def quarantine(
    session: AgentSession, decision_id: str, ring_id: str, reason: str
) -> dict[str, Any]:
    timer = GraphTimer()
    await require_own_decision(session, decision_id, timer)
    case = InvestigationCase(session.database, session.graph_name, decision_id, timer)
    try:
        policy = await case.quarantine(ring_id, reason)
    except QuarantineRefusedError as error:
        raise ToolRefusedError(str(error)) from error
    return {**asdict(policy), "graph_ms": timer.total_ms}
