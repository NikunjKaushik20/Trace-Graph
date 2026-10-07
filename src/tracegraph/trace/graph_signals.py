import math
from collections import Counter
from collections.abc import Iterable, Mapping

import numpy as np

from tracegraph.trace.settings import TraceSettings

SuccessEdge = tuple[str, str]


# Personalized PageRank over writer-provider success edges, restarting at the seed writers
def personalized_pagerank(
    success_edges: Iterable[SuccessEdge], seed_writers: Iterable[str], settings: TraceSettings
) -> dict[str, float]:
    return pagerank_from_counts(Counter(success_edges), seed_writers, settings)


# The same PageRank from edge counts; an edge seen n times weighs n, as in the paper
def pagerank_from_counts(
    edge_counts: Mapping[SuccessEdge, int], seed_writers: Iterable[str], settings: TraceSettings
) -> dict[str, float]:
    nodes = sorted({node for edge in edge_counts for node in edge})
    index = {node: position for position, node in enumerate(nodes)}
    seeds = sorted({writer for writer in seed_writers if writer in index})
    if not seeds:
        return {}
    walk = np.zeros((len(nodes), len(nodes)))
    for (writer, provider), count in edge_counts.items():
        walk[index[provider], index[writer]] += count
        walk[index[writer], index[provider]] += count
    walk /= walk.sum(axis=0)
    restart = np.zeros(len(nodes))
    restart[[index[seed] for seed in seeds]] = 1 / len(seeds)
    rank = restart.copy()
    for _ in range(settings.ppr_iterations):
        rank = settings.ppr_restart * restart + (1 - settings.ppr_restart) * (walk @ rank)
    return {node: float(rank[index[node]]) for node in nodes}


# Distance from the honest seeds: 0 for the best-reached provider, 1 for unreached ones
def ppr_distances(rank: Mapping[str, float], provider_ids: Iterable[str]) -> dict[str, float]:
    provider_list = list(provider_ids)
    best = max((rank.get(provider, 0.0) for provider in provider_list), default=0.0)
    if best <= 0:
        return dict.fromkeys(provider_list, 1.0)
    return {provider: 1 - rank.get(provider, 0.0) / best for provider in provider_list}


# Shannon entropy of who reported a provider's successes, scaled to 0..1 by the seed count
def counterparty_entropy(success_counts_by_writer: Mapping[str, int], seed_count: int) -> float:
    total = sum(success_counts_by_writer.values())
    if total == 0 or seed_count < 2:
        return 0.0
    entropy = 0.0
    for count in success_counts_by_writer.values():
        if count > 0:
            share = count / total
            entropy -= share * math.log2(share)
    return min(1.0, entropy / math.log2(seed_count))


# Edge-to-job Sybil signal: the share of a provider's reports not backed by a paid job
def sybil_ratio(reports_received: int, paid_jobs: int) -> float:
    if reports_received == 0:
        return 0.0
    return 1 - min(1.0, paid_jobs / reports_received)


# Clique signal: share of reviewer pairs that share a funder, or 1 if tied to a quarantined ring
def clique_score(reviewer_funders: Mapping[str, frozenset[str]], contaminated: bool) -> float:
    if contaminated:
        return 1.0
    reviewers = list(reviewer_funders)
    pairs = 0
    coordinated = 0
    for index, first in enumerate(reviewers):
        for second in reviewers[index + 1 :]:
            pairs += 1
            if reviewer_funders[first] & reviewer_funders[second]:
                coordinated += 1
    return coordinated / pairs if pairs else 0.0
