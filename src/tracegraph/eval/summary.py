import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any

from tracegraph.eval.outcomes import SeedResult


@dataclass(frozen=True)
class LaneSummary:
    lane: str
    adversary: str
    seeds: int
    mean: float
    se: float
    median: float
    p90: float
    max: float
    malicious_share: float
    mean_round_ms: float
    results: list[SeedResult]

    # The summary and its seeds as plain values for the save query
    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["results"] = [seed_row(result) for result in self.results]
        return row


# One seed's result without the per-round series
def seed_row(result: SeedResult) -> dict[str, Any]:
    row = asdict(result)
    del row["round_ms"], row["fraud_by_round"]
    return row


# Mean, standard error, median, 90th percentile and max fraud over a lane's seeds
def summarise(results: list[SeedResult]) -> LaneSummary:
    fraud = [float(result.fraud_sats) for result in results]
    jobs = sum(result.jobs for result in results)
    malicious = sum(result.malicious_jobs for result in results)
    timings = [ms for result in results for ms in result.round_ms]
    return LaneSummary(
        lane=results[0].lane,
        adversary=results[0].adversary,
        seeds=len(results),
        mean=statistics.fmean(fraud),
        se=statistics.stdev(fraud) / math.sqrt(len(fraud)) if len(fraud) > 1 else 0.0,
        median=statistics.median(fraud),
        p90=percentile(fraud, 0.90),
        max=max(fraud),
        malicious_share=malicious / jobs if jobs else 0.0,
        mean_round_ms=statistics.fmean(timings) if timings else 0.0,
        results=results,
    )


# Linear-interpolation percentile, the same rule as numpy's default
def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


# The demo seed, picked by rule: Alone minus Together closest to the median gap, under strat
def demo_seed(summaries: list[LaneSummary]) -> int | None:
    by_key = {(summary.lane, summary.adversary): summary for summary in summaries}
    alone, together = by_key.get(("alone", "strat")), by_key.get(("together", "strat"))
    if alone is None or together is None:
        return None
    together_fraud = {result.seed: result.fraud_sats for result in together.results}
    gaps = {
        result.seed: result.fraud_sats - together_fraud[result.seed]
        for result in alone.results
        if result.seed in together_fraud
    }
    if not gaps:
        return None
    middle = statistics.median(gaps.values())
    return min(gaps, key=lambda seed: (abs(gaps[seed] - middle), seed))
