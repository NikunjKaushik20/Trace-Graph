import pytest

from tests.agent.rule_model import RuleFollowingModel
from tracegraph.config import Settings
from tracegraph.eval.agent_cases import build_cases
from tracegraph.eval.graph_lane import run_graph_case
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.embeddings import HashingEmbedder

pytestmark = pytest.mark.falkordb

CASES = build_cases()


async def test_a_ring_case_is_investigated_and_an_honest_provider_paid(
    database: GraphDatabase,
) -> None:
    case = next(case for case in CASES if case.label == "ring")
    run = await run_graph_case(
        database, Settings(), RuleFollowingModel(), HashingEmbedder(384), case
    )
    assert run.investigated and run.quarantined and run.quarantine_backed
    assert run.hired is not None and not run.hired_malicious


async def test_a_clean_case_is_paid_without_investigating(database: GraphDatabase) -> None:
    case = next(case for case in CASES if case.label == "clean")
    run = await run_graph_case(
        database, Settings(), RuleFollowingModel(), HashingEmbedder(384), case
    )
    assert not run.investigated and run.hired is not None
    assert "agent-eval:" + case.case_id not in await database.list_graphs()
