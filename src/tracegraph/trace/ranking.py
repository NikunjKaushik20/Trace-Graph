import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from tracegraph.trace.graph_signals import personalized_pagerank, ppr_distances
from tracegraph.trace.settings import TraceSettings
from tracegraph.trace.utility import ProviderEvidence, ProviderScore, score_provider

DecisionStatus = Literal["confident", "flagged", "no_eligible_provider"]


@dataclass
class Ranking:
    ranked: list[ProviderScore]
    excluded: list[ProviderScore]
    flags: dict[str, list[str]]
    status: DecisionStatus

    # The provider TRACE would pick
    @property
    def top(self) -> ProviderScore | None:
        return self.ranked[0] if self.ranked else None

    # Flags as 'provider: flag' lines, the form stored on the Decision node
    @property
    def flag_lines(self) -> list[str]:
        return [f"{provider}: {flag}" for provider, flags in self.flags.items() for flag in flags]


# Scores every candidate, drops excluded ones and orders the rest by utility (greedy, no bandit)
def rank_candidates(
    evidence_by_provider: Mapping[str, ProviderEvidence],
    success_edges: Iterable[tuple[str, str]],
    seed_writers: list[str],
    settings: TraceSettings,
    tie_breaker: random.Random,
) -> Ranking:
    scores = score_candidates(evidence_by_provider, success_edges, seed_writers, settings)
    return order_scores(scores, settings, tie_breaker)


# Runs TRACE on every candidate, with PPR computed once for the whole candidate set
def score_candidates(
    evidence_by_provider: Mapping[str, ProviderEvidence],
    success_edges: Iterable[tuple[str, str]],
    seed_writers: list[str],
    settings: TraceSettings,
) -> list[ProviderScore]:
    rank = personalized_pagerank(success_edges, seed_writers, settings)
    distances = ppr_distances(rank, evidence_by_provider)
    return [
        score_provider(evidence, distances[provider_id], len(seed_writers), settings)
        for provider_id, evidence in evidence_by_provider.items()
    ]


# Orders eligible providers by utility, with seeded tie-breaking, and flags the hireable ones
def order_scores(
    scores: list[ProviderScore], settings: TraceSettings, tie_breaker: random.Random
) -> Ranking:
    shuffled = sorted(scores, key=lambda score: score.provider_id)
    tie_breaker.shuffle(shuffled)
    eligible = sorted((score for score in shuffled if score.eligible), key=lambda s: -s.utility)
    excluded = [score for score in shuffled if not score.eligible]
    flags = flags_for_hireable(eligible, settings)
    status = decision_status(eligible, flags)
    return Ranking(ranked=eligible, excluded=excluded, flags=flags, status=status)


# Whether the graph is confident, wants a closer look, or has nobody to pick
def decision_status(eligible: list[ProviderScore], flags: dict[str, list[str]]) -> DecisionStatus:
    if not eligible:
        return "no_eligible_provider"
    if flags:
        return "flagged"
    return "confident"


# Flags for every provider the buyer may hire, plus a close-call flag on the top pick
def flags_for_hireable(
    ranked: list[ProviderScore], settings: TraceSettings
) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}
    for score in ranked[: settings.hireable_count]:
        reasons = reasons_to_look_closer(score, settings)
        if reasons:
            flags[score.provider_id] = reasons
    if is_close_call(ranked, settings):
        flags.setdefault(ranked[0].provider_id, []).append("close_call")
    return flags


# Signs that one provider deserves a closer look before it is paid
def reasons_to_look_closer(score: ProviderScore, settings: TraceSettings) -> list[str]:
    reasons = []
    if score.successes + score.failures < settings.new_provider_outcomes:
        reasons.append("new_provider")
    if score.ignored_claims >= settings.uncounted_reports_flag:
        reasons.append("reports_from_uncounted_writers")
    if score.clique >= settings.coordinated_share:
        reasons.append("reviewers_share_funding")
    if score.sybil >= settings.sybil_share:
        reasons.append("reports_without_paid_jobs")
    if score.cusum >= settings.cusum_threshold / 2:
        reasons.append("recent_failures_rising")
    return reasons


# True when the top two providers both have evidence and are nearly tied
def is_close_call(ranked: list[ProviderScore], settings: TraceSettings) -> bool:
    if len(ranked) < 2:
        return False
    first, second = ranked[0], ranked[1]
    both_known = min(first.successes + first.failures, second.successes + second.failures) > 0
    return both_known and first.utility - second.utility < settings.close_call_gap
