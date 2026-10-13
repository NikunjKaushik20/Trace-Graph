from tracegraph.eval.ledger import EvidenceLedger
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.scoreboard import QUARANTINE_STATE, RECORD_SIM_DECISION
from tracegraph.investigation.case import InvestigationCase


# The flagged-case path from the agent prompt, scripted: trace the money, find the ring, block it
async def investigate(
    database: GraphDatabase,
    graph_name: str,
    ledger: EvidenceLedger,
    *,
    buyer_id: str,
    provider_id: str,
    round_index: int,
    timer: GraphTimer,
) -> bool:
    decision_id = f"dec-r{round_index}-{buyer_id}-{provider_id}"
    params = {"decision_id": decision_id, "buyer_id": buyer_id, "t": round_index}
    await database.run(graph_name, RECORD_SIM_DECISION, params, timer)
    case = InvestigationCase(database, graph_name, decision_id, timer)
    writer_id = ledger.ignored_writers[provider_id][0]
    path = await case.trace_funding(writer_id, provider_id)
    ring = await case.look_for_ring(provider_id)
    if not (path.found and ring.is_ring and ring.ring_id):
        return False
    reason = f"Praise for {provider_id} is paid for through {ring.hub_id}."
    await case.quarantine(ring.ring_id, reason)
    rows = await database.rows(graph_name, QUARANTINE_STATE, {}, timer)
    ledger.apply_quarantine(list(rows[0]["quarantined"]), list(rows[0]["contaminated"]))
    return True
