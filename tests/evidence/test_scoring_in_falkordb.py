import random

import pytest

from tests.evidence.small_market import build_small_market
from tracegraph.evidence.reader import EvidenceRequest
from tracegraph.evidence.rules import GuardRules
from tracegraph.evidence.scoring import score_job_candidates
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.udf_loader import TRACE_LIBRARY, load_trace_udf
from tracegraph.trace.settings import TraceSettings

pytestmark = pytest.mark.falkordb

SETTINGS = TraceSettings()


@pytest.mark.parametrize("rules", [GuardRules.closed_fleet(), GuardRules.unguarded()])
async def test_udf_and_python_rank_the_same_way(
    database: GraphDatabase, graph_name: str, rules: GuardRules
) -> None:
    await build_small_market(database, graph_name)
    await load_trace_udf(database)
    request = EvidenceRequest(graph_name, "buyer-2", "summarise", 10, rules)
    in_database = await score_job_candidates(database, request, SETTINGS, "udf", random.Random(3))
    in_python = await score_job_candidates(database, request, SETTINGS, "python", random.Random(3))
    assert [s.provider_id for s in in_database.ranking.ranked] == [
        s.provider_id for s in in_python.ranking.ranked
    ]
    for udf_score, python_score in zip(
        in_database.ranking.ranked, in_python.ranking.ranked, strict=True
    ):
        assert udf_score.utility == pytest.approx(python_score.utility, abs=1e-9)
    assert in_database.graph_ms >= 0


async def test_a_server_that_forgot_the_udf_gets_it_back_on_the_next_score(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    await load_trace_udf(database)
    await (await database.connected_client()).udf_delete(TRACE_LIBRARY)
    request = EvidenceRequest(graph_name, "buyer-2", "summarise", 10, GuardRules.closed_fleet())
    scored = await score_job_candidates(database, request, SETTINGS, "udf", random.Random(3))
    assert scored.ranking.ranked


async def test_unguarded_memory_lets_sybil_praise_lift_the_ring(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    await load_trace_udf(database)
    closed = EvidenceRequest(graph_name, "buyer-2", "summarise", 10, GuardRules.closed_fleet())
    open_memory = EvidenceRequest(graph_name, "buyer-2", "summarise", 10, GuardRules.unguarded())
    guarded = await score_job_candidates(database, closed, SETTINGS, "udf", random.Random(1))
    poisoned = await score_job_candidates(database, open_memory, SETTINGS, "udf", random.Random(1))
    ring_when_guarded = next(s for s in guarded.ranking.ranked if s.provider_id == "p-ring")
    ring_when_poisoned = next(s for s in poisoned.ranking.ranked if s.provider_id == "p-ring")
    assert ring_when_guarded.successes == 0
    assert ring_when_guarded.ignored_claims == 2
    assert ring_when_poisoned.successes == 2
