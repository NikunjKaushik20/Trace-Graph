from dataclasses import dataclass, field

from tracegraph.eval.contract import Adversary, MarketContract
from tracegraph.eval.population import SimMarket


@dataclass
class SeedResult:
    lane: str
    adversary: str
    seed: int
    fraud_sats: int = 0
    jobs: int = 0
    malicious_jobs: int = 0
    attacker_spend_sats: int = 0
    quarantined_at_round: int | None = None
    round_ms: list[float] = field(default_factory=list)
    fraud_by_round: list[int] = field(default_factory=list)


# Whether a job succeeds, from the provider's type, the price and one pre-drawn random number
def job_succeeds(
    contract: MarketContract,
    market: SimMarket,
    adversary: Adversary,
    *,
    provider_id: str,
    price_sats: int,
    jobs_done: int,
    draw: float,
) -> bool:
    if not market.is_malicious(provider_id):
        return draw >= contract.honest_failure_rate
    turned = adversary == "strat" or jobs_done >= contract.calib_honest_jobs
    if turned and price_sats >= contract.high_price_sats:
        return draw >= contract.high_price_default_rate
    return draw >= contract.honest_failure_rate


# Counts one finished job towards the seed's totals; fraud is sats lost to a malicious default
def count_job(
    result: SeedResult, market: SimMarket, provider_id: str, price_sats: int, ok: bool
) -> None:
    result.jobs += 1
    if market.is_malicious(provider_id):
        result.malicious_jobs += 1
        if not ok:
            result.fraud_sats += price_sats
