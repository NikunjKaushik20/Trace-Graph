import random
from dataclasses import dataclass

from tracegraph.eval.ledger import BuyerView
from tracegraph.trace.graph_signals import pagerank_from_counts, ppr_distances
from tracegraph.trace.ranking import reasons_to_look_closer
from tracegraph.trace.settings import TraceSettings
from tracegraph.trace.utility import ProviderEvidence, ProviderScore, score_provider


@dataclass
class ScoredView:
    eligible: list[ProviderScore]
    unseen: ProviderScore
    unseen_ids: list[str]

    # The providers a buyer may hire: the top few by utility, providers with no record last
    def hireable(self, count: int) -> list[ProviderScore]:
        return [score for score in self.eligible[:count] if score.utility >= self.unseen.utility]


# Scores a buyer's view with TRACE; providers nobody has reported on share one blank score
def score_view(view: BuyerView, all_provider_ids: list[str], settings: TraceSettings) -> ScoredView:
    rank = pagerank_from_counts(view.edge_counts, view.seed_writers, settings)
    distances = ppr_distances(rank, view.evidence)
    seed_count = len(view.seed_writers)
    scores = [
        score_provider(evidence, distances[provider_id], seed_count, settings)
        for provider_id, evidence in view.evidence.items()
    ]
    eligible = sorted(
        (score for score in scores if score.eligible), key=lambda score: -score.utility
    )
    unseen = score_provider(ProviderEvidence(provider_id="unseen"), 1.0, seed_count, settings)
    unseen_ids = [pid for pid in all_provider_ids if pid not in view.evidence]
    return ScoredView(eligible, unseen, unseen_ids)


# Greedy pick: the highest utility, with ties broken at random as TRACE does
def pick_greedy(scored: ScoredView, rng: random.Random) -> str | None:
    utilities = [score.utility for score in scored.eligible]
    if scored.unseen_ids:
        utilities.append(scored.unseen.utility)
    if not utilities:
        return None
    best = max(utilities)
    tied = sorted(score.provider_id for score in scored.eligible if score.utility == best)
    if scored.unseen_ids and scored.unseen.utility == best:
        tied += scored.unseen_ids
    return rng.choice(tied)


# The first hireable provider praised by writers the guard did not count, if any
def provider_to_investigate(
    scored: ScoredView, settings: TraceSettings, already_checked: set[str]
) -> str | None:
    for score in scored.hireable(settings.hireable_count):
        reasons = reasons_to_look_closer(score, settings)
        if "reports_from_uncounted_writers" in reasons and score.provider_id not in already_checked:
            return score.provider_id
    return None
