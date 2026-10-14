import pytest

from tests.eval.memory_market import MemoryMarketDatabase
from tracegraph.eval.contract import MarketContract
from tracegraph.eval.lanes import LANES_BY_NAME
from tracegraph.eval.market_run import MarketRun
from tracegraph.graph.connection import GraphDatabase

pytestmark = pytest.mark.falkordb

SMALL = MarketContract(providers=200, rounds=30, ring_providers=10, sybil_writers=8)


@pytest.mark.parametrize("lane", ["alone", "poisoned", "guarded_half_hidden", "bad_mouthed"])
async def test_the_cypher_guard_gives_the_same_market_as_the_reference(
    database: GraphDatabase, lane: str
) -> None:
    in_falkordb = await MarketRun(database, SMALL, LANES_BY_NAME[lane], "strat", 1000).play()
    reference = await MarketRun(
        MemoryMarketDatabase(), SMALL, LANES_BY_NAME[lane], "strat", 1000
    ).play()
    assert in_falkordb.fraud_sats == reference.fraud_sats
    assert in_falkordb.malicious_jobs == reference.malicious_jobs


async def test_the_quarantine_lane_finds_and_blocks_the_ring(database: GraphDatabase) -> None:
    run = MarketRun(database, SMALL, LANES_BY_NAME["quarantine"], "strat", 1000)
    result = await run.play()
    assert result.quarantined_at_round is not None
    [ledger] = run.ledgers.values()
    blocked = {pid for pid, evidence in ledger.shared.items() if evidence.quarantined}
    assert blocked == set(run.market.ring)


async def test_the_lane_graphs_are_removed_afterwards(database: GraphDatabase) -> None:
    await MarketRun(database, SMALL, LANES_BY_NAME["together"], "calib", 1003).play()
    leftovers = [name for name in await database.list_graphs() if "together-calib:1003" in name]
    assert leftovers == []
