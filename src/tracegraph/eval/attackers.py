import random
from collections import Counter

from tracegraph.eval.contract import MarketContract
from tracegraph.eval.population import SimMarket
from tracegraph.market.records import SettledJob


# Fake five-star jobs: Sybils pay ring providers and report success, money the ring gets back
def praise_jobs(
    contract: MarketContract, market: SimMarket, round_index: int, rng: random.Random
) -> list[SettledJob]:
    jobs = []
    for number in range(contract.fake_writes_per_round):
        job_id = f"j{round_index}-x{number}"
        jobs.append(
            SettledJob(
                job_id=job_id,
                payment_id=f"pay-{job_id}",
                payer_id=rng.choice(market.sybil_ids),
                provider_id=rng.choice(market.ring),
                price_sats=rng.randint(contract.min_price_sats, contract.max_price_sats),
                ok=True,
                t=round_index,
            )
        )
    return jobs


# Fake failures on the honest providers buyers trust most, so buyers drift to worse ones
def badmouth_jobs(
    contract: MarketContract,
    market: SimMarket,
    round_index: int,
    buyer_tally: Counter[str],
    rng: random.Random,
) -> list[SettledJob]:
    honest = [pid for pid in market.provider_ids if not market.is_malicious(pid)]
    tally = {pid: buyer_tally[pid] for pid in honest}
    jobs = []
    for number in range(contract.fake_writes_per_round):
        best = max(tally.values())
        target = rng.choice([pid for pid, score in tally.items() if score == best])
        tally[target] -= 1
        job_id = f"j{round_index}-x{number}"
        jobs.append(
            SettledJob(
                job_id=job_id,
                payment_id=f"pay-{job_id}",
                payer_id=rng.choice(market.sybil_ids),
                provider_id=target,
                price_sats=rng.randint(contract.min_price_sats, contract.max_price_sats),
                ok=False,
                t=round_index,
            )
        )
    return jobs
