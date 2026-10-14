import random
import time

import pytest

from tracegraph.evidence.decisions import DecisionContext, record_decision
from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.evidence.rules import GuardRules
from tracegraph.evidence.scoring import score_job_candidates
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.udf_loader import load_trace_udf
from tracegraph.llm.text_model import ScriptedModel
from tracegraph.market.escrow import Escrow, HireRefusedError, HireRequest
from tracegraph.market.hiring import Marketplace
from tracegraph.market.paywall import MockLightning
from tracegraph.market.providers import ProviderAgent, work_for
from tracegraph.market.roster import demo_market
from tracegraph.market.seed import write_market
from tracegraph.market.tasks import PlannedJob, TaskPlan, open_task
from tracegraph.market.work import WorkOrder
from tracegraph.trace.settings import TraceSettings

pytestmark = pytest.mark.falkordb

TEXT = "FalkorDB stores graphs as sparse matrices and answers Cypher queries quickly."
SETTINGS = TraceSettings()


# A model that summarises honestly when asked to work and passes work when asked to judge
def scripted_llm(system: str, prompt: str) -> str:
    if system.startswith("You check paid work"):
        return "PASS: summary matches the input"
    return '{"summary": "FalkorDB keeps graphs in sparse matrices and runs Cypher fast."}'


# The demo market in a test graph, with live provider agents in front of it
async def demo_marketplace(database: GraphDatabase, graph_name: str) -> Marketplace:
    spec = demo_market(time.time())
    await write_market(database, graph_name, spec, embedding_dimensions=8)
    await load_trace_udf(database)
    model = ScriptedModel(scripted_llm)
    lightning = MockLightning()
    agents = {
        provider_id: ProviderAgent(
            provider_id, work_for(behaviour, model, random.Random(1)), lightning
        )
        for provider_id, behaviour in spec.behaviours.items()
    }
    return Marketplace(Escrow(database, graph_name), lightning, agents, model)


async def test_a_summary_job_is_scored_hired_judged_and_released(
    database: GraphDatabase, graph_name: str
) -> None:
    market = await demo_marketplace(database, graph_name)
    plan = TaskPlan(
        "task-1", "buyer-1", TEXT, [PlannedJob("job-1", "summarise", TEXT)], time.time()
    )
    await open_task(database, graph_name, plan)
    request = EvidenceRequest(
        graph_name, "buyer-1", "summarise", time.time(), GuardRules.closed_fleet()
    )
    scored = await score_job_candidates(database, request, SETTINGS, "udf", random.Random(1))
    assert scored.ranking.top is not None
    assert scored.ranking.top.provider_id in {"prov-summa", "prov-brevity"}
    assert "prov-quickdigest" in scored.ranking.flags
    context = DecisionContext(
        graph_name, "dec-1", "job-1", "buyer-1", "together", "closed", time.time()
    )
    await record_decision(database, context, scored)

    top = scored.ranking.top
    order = WorkOrder("job-1", "summarise", TEXT, scored.prices[top.provider_id])
    hired = await market.hire_with_escrow(
        HireRequest("buyer-1", "job-1", top.provider_id, "dec-1"), order
    )
    assert hired.payment.balance_sats == 1000 - order.price_sats
    settled = await market.settle(order, hired.delivery)
    assert settled.verdict.passed
    assert settled.payment.status == "released"
    assert settled.payment.balance_sats == 1000 - order.price_sats


async def test_the_escrow_refuses_a_provider_outside_the_ranked_set(
    database: GraphDatabase, graph_name: str
) -> None:
    market = await demo_marketplace(database, graph_name)
    plan = TaskPlan(
        "task-1", "buyer-1", TEXT, [PlannedJob("job-1", "summarise", TEXT)], time.time()
    )
    await open_task(database, graph_name, plan)
    request = EvidenceRequest(
        graph_name, "buyer-1", "summarise", time.time(), GuardRules.closed_fleet()
    )
    scored = await score_job_candidates(database, request, SETTINGS, "udf", random.Random(1))
    context = DecisionContext(
        graph_name, "dec-1", "job-1", "buyer-1", "together", "closed", time.time()
    )
    await record_decision(database, context, scored)
    excluded = scored.ranking.excluded[0].provider_id
    order = WorkOrder("job-1", "summarise", TEXT, scored.prices[excluded])
    with pytest.raises(HireRefusedError, match="not in the top 3"):
        await market.hire_with_escrow(HireRequest("buyer-1", "job-1", excluded, "dec-1"), order)
