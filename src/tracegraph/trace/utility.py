from dataclasses import dataclass, field

from tracegraph.trace.graph_signals import clique_score, counterparty_entropy, sybil_ratio
from tracegraph.trace.reliability import (
    bayesian_lcb,
    cusum_statistic,
    exclusion_reason,
    smoothed_default_rate,
)
from tracegraph.trace.settings import TraceSettings


@dataclass
class ProviderEvidence:
    provider_id: str
    outcomes: list[bool] = field(default_factory=list)
    success_counts_by_writer: dict[str, int] = field(default_factory=dict)
    reviewer_funders: dict[str, frozenset[str]] = field(default_factory=dict)
    reports_received: int = 0
    paid_jobs: int = 0
    ignored_claims: int = 0
    contaminated: bool = False
    quarantined: bool = False
    has_capability: bool = True


@dataclass
class ProviderScore:
    provider_id: str
    utility: float
    lcb: float
    risk: float
    ppr_distance: float
    entropy: float
    capability: float
    sybil: float
    clique: float
    cusum: float
    successes: int
    failures: int
    ignored_claims: int
    excluded_because: str | None

    # True when no hard filter removed this provider
    @property
    def eligible(self) -> bool:
        return self.excluded_because is None


# Scores one provider with TRACE's seven-term utility from its counted evidence
def score_provider(
    evidence: ProviderEvidence, ppr_distance: float, seed_count: int, settings: TraceSettings
) -> ProviderScore:
    weights = settings.weights
    successes = sum(1 for succeeded in evidence.outcomes if succeeded)
    failures = len(evidence.outcomes) - successes
    lcb = bayesian_lcb(successes, failures, settings)
    risk = smoothed_default_rate(evidence.outcomes, settings)
    entropy = counterparty_entropy(evidence.success_counts_by_writer, seed_count)
    capability = 1.0 if evidence.has_capability else 0.0
    sybil = sybil_ratio(evidence.reports_received, evidence.paid_jobs)
    clique = clique_score(evidence.reviewer_funders, evidence.contaminated)
    utility = (
        weights.trace * lcb
        - weights.risk * risk
        - weights.ppr_distance * ppr_distance
        + weights.entropy * entropy
        + weights.capability * capability
        - weights.sybil * sybil
        - weights.clique * clique
    )
    return ProviderScore(
        provider_id=evidence.provider_id,
        utility=utility,
        lcb=lcb,
        risk=risk,
        ppr_distance=ppr_distance,
        entropy=entropy,
        capability=capability,
        sybil=sybil,
        clique=clique,
        cusum=cusum_statistic(evidence.outcomes, settings),
        successes=successes,
        failures=failures,
        ignored_claims=evidence.ignored_claims,
        excluded_because=why_excluded(evidence, settings),
    )


# Hard filters that remove a provider before ranking
def why_excluded(evidence: ProviderEvidence, settings: TraceSettings) -> str | None:
    if evidence.quarantined:
        return "quarantined"
    if not evidence.has_capability:
        return "no_capability"
    return exclusion_reason(evidence.outcomes, settings)
