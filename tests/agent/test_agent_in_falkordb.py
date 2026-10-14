import pytest

from tests.agent.rule_model import RuleFollowingModel
from tests.market.test_paid_job_in_falkordb import demo_marketplace
from tracegraph.agent.loop import BuyerAgent
from tracegraph.agent.session import AgentSession
from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.embeddings import HashingEmbedder

pytestmark = pytest.mark.falkordb

PAGE = "FalkorDB stores graphs as sparse matrices and answers Cypher queries with linear algebra."
RING = ["prov-quickdigest", "prov-tagstar", "prov-transfast"]


# A buyer agent on the test graph, driven by the rule-following stand-in for the LLM
async def agent_for(
    database: GraphDatabase, graph_name: str, buyer_id: str, seed: bool
) -> BuyerAgent:
    market = await demo_marketplace(database, graph_name) if seed else None
    session = AgentSession(
        database,
        Settings(shared_graph=graph_name),
        buyer_id,
        marketplace=market,
        embedder=HashingEmbedder(8),
    )
    return BuyerAgent(session, RuleFollowingModel())


async def test_a_flagged_job_is_investigated_quarantined_and_then_paid_honestly(
    database: GraphDatabase, graph_name: str
) -> None:
    agent = await agent_for(database, graph_name, "buyer-1", seed=True)
    run = await agent.run_task("task-1", f"Summarise: {PAGE}")
    [job] = run.jobs
    assert job.tool_path[:5] == [
        "recall_memory",
        "trace_score",
        "funding_path",
        "find_ring",
        "quarantine",
    ]
    assert "write_lesson" in job.tool_path
    quarantine = next(step for step in job.steps if step.name == "quarantine")
    assert isinstance(quarantine.result, dict) and quarantine.result["covered"] == RING
    settle = next(step for step in job.steps if step.name == "settle")
    assert isinstance(settle.result, dict)
    assert settle.result["status"] == "released"
    assert settle.result["provider_id"] not in RING
    assert job.citations.passed and not job.citations.fell_back_to_receipt


async def test_another_buyer_skips_the_ring_without_being_told(
    database: GraphDatabase, graph_name: str
) -> None:
    first = await agent_for(database, graph_name, "buyer-1", seed=True)
    await first.run_task("task-1", f"Summarise: {PAGE}")
    second = await agent_for(database, graph_name, "buyer-3", seed=False)
    second.session.marketplace = first.session.marketplace
    run = await second.run_task("task-2", f"Translate: {PAGE}")
    [job] = run.jobs
    assert "find_ring" not in job.tool_path
    score = next(step for step in job.steps if step.name == "trace_score")
    assert isinstance(score.result, dict)
    excluded = {entry["provider_id"]: entry["reason"] for entry in score.result["excluded"]}
    assert excluded["prov-transfast"] == "quarantined"
