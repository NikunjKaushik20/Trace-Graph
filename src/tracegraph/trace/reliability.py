import math
from collections.abc import Sequence

from tracegraph.trace.settings import TraceSettings


# Lower end of a Wilson interval for a success share out of n trials
def wilson_lower_bound(successes: float, trials: float, z: float) -> float:
    if trials <= 0:
        return 0.0
    share = successes / trials
    z_squared = z * z
    centre = share + z_squared / (2 * trials)
    margin = z * math.sqrt(share * (1 - share) / trials + z_squared / (4 * trials * trials))
    lower = (centre - margin) / (1 + z_squared / trials)
    return min(1.0, max(0.0, lower))


# TRACE's Bayesian LCB: completion rate under a Beta(1,3) prior, 95% lower bound
def bayesian_lcb(successes: int, failures: int, settings: TraceSettings) -> float:
    alpha = successes + settings.prior_successes
    beta = failures + settings.prior_failures
    return wilson_lower_bound(alpha, alpha + beta, settings.lcb_z)


# Lower bound on how often a provider fails, from its observed outcomes only
def failure_rate_lower_bound(successes: int, failures: int, settings: TraceSettings) -> float:
    return wilson_lower_bound(failures, successes + failures, settings.failure_bound_z)


# Exponentially smoothed default probability over outcomes in time order
def smoothed_default_rate(outcomes: Sequence[bool], settings: TraceSettings) -> float:
    rate = 0.0
    for succeeded in outcomes:
        failed = 0.0 if succeeded else 1.0
        rate = (1 - settings.risk_smoothing) * rate + settings.risk_smoothing * failed
    return rate


# CUSUM statistic that grows on failures and shrinks on successes
def cusum_statistic(outcomes: Sequence[bool], settings: TraceSettings) -> float:
    statistic = 0.0
    for succeeded in outcomes:
        failed = 0.0 if succeeded else 1.0
        statistic = max(0.0, statistic + failed - (1 - settings.cusum_reference))
    return statistic


# Reason a provider is excluded on its own record, or None if it may be picked
def exclusion_reason(outcomes: Sequence[bool], settings: TraceSettings) -> str | None:
    if cusum_statistic(outcomes, settings) > settings.cusum_threshold:
        return "cusum_alarm"
    successes = sum(1 for succeeded in outcomes if succeeded)
    failures = len(outcomes) - successes
    if failure_rate_lower_bound(successes, failures, settings) > settings.honest_failure_rate:
        return "fails_more_than_honest"
    return None
