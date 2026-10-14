import random
import time

import pytest

from tracegraph.evidence.decisions import DecisionContext, record_decision
from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.evidence.rules import GuardRules
from tracegraph.evidence.scoring import score_job_candidates
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.udf_loader import load_trace_udf
from tracegraph.investigation.case import InvestigationCase, QuarantineRefusedError
from tracegraph.investigation.funding import funding_path
from tracegraph.investigation.rings import find_ring
from tracegraph.market.roster import SYBIL_WRITERS, demo_market
from tracegraph.market.seed import write_market
from tracegraph.market.tasks import PlannedJob, TaskPlan, open_task
from tracegraph.trace.settings import TraceSettings

pytestmark = pytest.mark.falkordb

RING = ["prov-quickdigest", "prov-tagstar", "prov-transfast"]


# Seeds the demo market and records one summarise decision for buyer-1
async def market_with_a_decision(database: GraphDatabase, graph_name: str) -> None:
    await write_market(database, graph_name, demo_market(time.time()), embedding_dimensions=8)
    await load_trace_udf(database)
    plan = TaskPlan(
        "task-1", "buyer-1", "text", [PlannedJob("job-1", "summarise", "text")], time.time()
    )
    await open_task(database, graph_name, plan)
    request = EvidenceRequest(
        graph_name, "buyer-1", "summarise", time.time(), GuardRules.closed_fleet()
    )
    scored = await score_job_candidates(database, request, TraceSettings(), "udf", random.Random(1))
    context = DecisionContext(
        graph_name, "dec-1", "job-1", "buyer-1", "together", "closed", time.time()
    )
    await record_decision(database, context, scored)


async def test_find_ring_names_the_ring_its_writers_and_its_hub(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    report = await find_ring(database, graph_name, "prov-quickdigest")
    assert report.is_ring
    assert report.providers == sorted(RING)
    assert report.writers == sorted(SYBIL_WRITERS)
    assert report.hub_id == "root-ring-hub"
    assert report.outside_praise == 60


async def test_an_honest_provider_is_not_a_ring(database: GraphDatabase, graph_name: str) -> None:
    await market_with_a_decision(database, graph_name)
    report = await find_ring(database, graph_name, "prov-summa")
    assert not report.is_ring


async def test_funding_path_joins_a_sybil_to_the_ring_through_the_hub(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    path = await funding_path(database, graph_name, "sybil-01", "prov-quickdigest")
    assert path.found
    assert "root-ring-hub" in path.shared_funders
    honest = await funding_path(database, graph_name, "buyer-1", "prov-quickdigest")
    assert not honest.found


async def test_quarantine_needs_both_investigations_then_covers_the_whole_ring(
    database: GraphDatabase, graph_name: str
) -> None:
    await market_with_a_decision(database, graph_name)
    case = InvestigationCase(database, graph_name, "dec-1")
    report = await case.look_for_ring("prov-quickdigest")
    assert report.ring_id is not None
    with pytest.raises(QuarantineRefusedError):
        await case.quarantine(report.ring_id, "ring")
    await case.trace_funding("buyer-1", "prov-quickdigest")
    with pytest.raises(QuarantineRefusedError):
        await case.quarantine(report.ring_id, "ring")
    await case.trace_funding("sybil-01", "prov-quickdigest")
    policy = await case.quarantine(report.ring_id, "ring")
    assert policy.covered == sorted(RING)
    assert policy.created_by == "buyer-1"

    request = EvidenceRequest(
        graph_name, "buyer-3", "translate", time.time(), GuardRules.closed_fleet()
    )
    scored = await score_job_candidates(database, request, TraceSettings(), "udf", random.Random(1))
    reasons = {score.provider_id: score.excluded_because for score in scored.ranking.excluded}
    assert reasons["prov-transfast"] == "quarantined"
