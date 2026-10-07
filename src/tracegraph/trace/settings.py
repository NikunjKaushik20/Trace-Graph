from dataclasses import dataclass


@dataclass(frozen=True)
class UtilityWeights:
    trace: float = 0.40
    risk: float = 0.30
    ppr_distance: float = 0.15
    entropy: float = 0.10
    capability: float = 0.10
    sybil: float = 0.35
    clique: float = 0.25


@dataclass(frozen=True)
class TraceSettings:
    weights: UtilityWeights = UtilityWeights()
    prior_successes: float = 1.0
    prior_failures: float = 3.0
    lcb_z: float = 1.96
    failure_bound_z: float = 1.645
    honest_failure_rate: float = 0.10
    risk_smoothing: float = 0.3
    cusum_reference: float = 0.625
    cusum_threshold: float = 4.2
    ppr_restart: float = 0.15
    ppr_iterations: int = 40
    new_provider_outcomes: int = 3
    uncounted_reports_flag: int = 3
    coordinated_share: float = 0.3
    sybil_share: float = 0.5
    close_call_gap: float = 0.005
    hireable_count: int = 3
