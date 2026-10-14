from tests.eval.memory_market import MemoryMarketDatabase
from tracegraph.eval.contract import MarketContract
from tracegraph.eval.lanes import LANES_BY_NAME
from tracegraph.eval.market_run import MarketRun
from tracegraph.eval.summary import demo_seed, summarise

SMALL = MarketContract(providers=200, rounds=30, ring_providers=10, sybil_writers=8)


# Plays one lane on one seed of the small market against the in-memory database
async def play(lane: str, seed: int = 1000) -> MarketRun:
    run = MarketRun(MemoryMarketDatabase(), SMALL, LANES_BY_NAME[lane], "strat", seed)
    await run.play()
    return run


# Every Sybil whose praise was counted somewhere in the run's shared evidence
def counted_sybils(run: MarketRun) -> set[str]:
    [ledger] = run.ledgers.values()
    return {
        writer
        for evidence in ledger.shared.values()
        for writer in evidence.success_counts_by_writer
        if writer.startswith("sybil")
    }


async def test_the_same_lane_and_seed_always_gives_the_same_result() -> None:
    first, second = await play("together"), await play("together")
    assert first.result.fraud_sats == second.result.fraud_sats
    assert first.result.jobs == second.result.jobs == SMALL.buyers * SMALL.rounds


async def test_unguarded_praise_counts_and_the_guard_drops_all_of_it() -> None:
    assert counted_sybils(await play("poisoned"))
    assert counted_sybils(await play("guarded")) == set()


async def test_with_half_the_funding_hidden_only_the_hidden_sybils_count() -> None:
    run = await play("guarded_half_hidden")
    hidden = set(run.market.sybil_ids) - run.market.visible_sybils
    assert counted_sybils(run)
    assert counted_sybils(run) <= hidden


async def test_alone_gives_each_buyer_its_own_graph() -> None:
    run = await play("alone")
    assert sorted(ledger.seed_writers[0] for ledger in run.ledgers.values()) == sorted(
        run.market.buyer_ids
    )


async def test_the_demo_seed_is_the_one_closest_to_the_median_gap() -> None:
    seeds = (1000, 1001, 1002)
    alone = summarise([(await play("alone", seed)).result for seed in seeds])
    together = summarise([(await play("together", seed)).result for seed in seeds])
    gaps = {
        first.seed: first.fraud_sats - second.fraud_sats
        for first, second in zip(alone.results, together.results, strict=True)
    }
    chosen = demo_seed([alone, together])
    assert chosen is not None
    assert gaps[chosen] == sorted(gaps.values())[1]
