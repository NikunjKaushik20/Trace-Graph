import time

import pytest

from tests.market.test_paid_job_in_falkordb import demo_marketplace
from tracegraph.agent.session import AgentSession, ToolRefusedError
from tracegraph.agent.tools import deciding, explaining
from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.outcomes import RECORD_UNPAID_REPORTS
from tracegraph.market.tasks import PlannedJob, TaskPlan, open_task

pytestmark = pytest.mark.falkordb

TEXT = "FalkorDB stores graphs as sparse matrices and answers Cypher with linear algebra."


# Buyer 1 scores a summary job on the seeded demo market and returns the decision id
async def scored_decision(database: GraphDatabase, graph_name: str) -> tuple[AgentSession, str]:
    await demo_marketplace(database, graph_name)
    plan = TaskPlan(
        "task-1", "buyer-1", TEXT, [PlannedJob("job-1", "summarise", TEXT)], time.time()
    )
    await open_task(database, graph_name, plan)
    session = AgentSession(database, Settings(shared_graph=graph_name), "buyer-1")
    decision = await deciding.trace_score(session, "job-1")
    return session, str(decision["decision_id"])


async def test_turning_the_guard_off_lifts_the_ring_provider_but_not_to_the_top(
    database: GraphDatabase, graph_name: str
) -> None:
    session, decision_id = await scored_decision(database, graph_name)
    result = await explaining.what_if(session, decision_id, "unguarded")
    assert result["replay_matches_record"] is True
    assert result["changed"] is False
    assert result["top_used"] == "prov-summa"
    ring = next(s for s in result["shifts"] if s["provider_id"] == "prov-quickdigest")
    assert ring["reports_counted_now"] == 20
    assert "root-ring-hub" in ring["shared_funders"]
    assert ring["utility_after"] > ring["utility_before"]
    assert result["summary"].startswith("With the guard off, TRACE would still rank prov-summa")


async def test_reviews_written_after_the_decision_do_not_leak_into_its_replay(
    database: GraphDatabase, graph_name: str
) -> None:
    session, decision_id = await scored_decision(database, graph_name)
    later = [
        {"writer_id": "sybil-01", "provider_id": "prov-quickdigest", "ok": True, "t": time.time()}
        for _ in range(5)
    ]
    await database.run(graph_name, RECORD_UNPAID_REPORTS, {"reports": later})
    result = await explaining.what_if(session, decision_id, "unguarded")
    ring = next(s for s in result["shifts"] if s["provider_id"] == "prov-quickdigest")
    assert ring["reports_counted_now"] == 20


async def test_an_unknown_decision_is_refused(database: GraphDatabase, graph_name: str) -> None:
    session = AgentSession(database, Settings(shared_graph=graph_name), "buyer-1")
    with pytest.raises(ToolRefusedError):
        await explaining.what_if(session, "dec-nothing-1", "unguarded")
