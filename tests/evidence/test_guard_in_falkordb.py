import pytest

from tests.evidence.small_market import build_small_market
from tracegraph.evidence.reader import EvidenceRequest, read_candidate_evidence
from tracegraph.evidence.rules import GuardRules
from tracegraph.graph.connection import GraphDatabase

pytestmark = pytest.mark.falkordb


# Reads the evidence buyer-2 sees under the given guard rules
async def read_as_buyer_two(
    database: GraphDatabase, graph_name: str, rules: GuardRules
) -> dict[str, list[str | None]]:
    request = EvidenceRequest(graph_name, "buyer-2", "summarise", 10, rules)
    candidates = await read_candidate_evidence(database, request)
    reasons: dict[str, list[str | None]] = {}
    for report in candidates.reports:
        reasons.setdefault(report.writer_id, []).append(report.ignored_because)
    return reasons


async def test_closed_fleet_ignores_writers_that_are_not_admitted(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    reasons = await read_as_buyer_two(database, graph_name, GuardRules.closed_fleet())
    assert reasons["buyer-1"] == [None]
    assert reasons["sybil-1"] == ["writer_not_admitted"]
    assert reasons["sybil-2"] == ["writer_not_admitted"]


async def test_funding_check_catches_writers_funded_like_the_provider(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    reasons = await read_as_buyer_two(database, graph_name, GuardRules.open_with_funding_check())
    assert reasons["buyer-1"] == [None]
    assert reasons["sybil-1"] == ["shares_funding_with_provider"]
    assert reasons["sybil-2"] == ["shares_funding_with_provider"]


async def test_unguarded_memory_counts_every_write(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    reasons = await read_as_buyer_two(database, graph_name, GuardRules.unguarded())
    assert all(reason == [None] for reason in reasons.values())


async def test_other_buyers_reports_wait_for_the_visibility_delay(
    database: GraphDatabase, graph_name: str
) -> None:
    await build_small_market(database, graph_name)
    request = EvidenceRequest(graph_name, "buyer-2", "summarise", 0, GuardRules.unguarded())
    candidates = await read_candidate_evidence(database, request)
    assert candidates.reports == []
