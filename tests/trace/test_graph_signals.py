import pytest

from tracegraph.trace.graph_signals import (
    clique_score,
    counterparty_entropy,
    personalized_pagerank,
    ppr_distances,
    sybil_ratio,
)
from tracegraph.trace.settings import TraceSettings

SETTINGS = TraceSettings()


def test_ppr_reaches_providers_used_by_honest_seeds_only() -> None:
    edges = [("buyer-1", "p-good"), ("buyer-2", "p-good"), ("sybil-1", "p-ring")]
    rank = personalized_pagerank(edges, ["buyer-1", "buyer-2"], SETTINGS)
    assert rank["p-good"] > 0
    assert rank.get("p-ring", 0.0) == 0.0


def test_ppr_distance_is_zero_for_best_and_one_for_unreached() -> None:
    distances = ppr_distances({"p-good": 0.4, "p-other": 0.1}, ["p-good", "p-other", "p-new"])
    assert distances["p-good"] == 0.0
    assert distances["p-new"] == 1.0
    assert 0.0 < distances["p-other"] < 1.0


def test_ppr_with_no_seeds_in_graph_gives_empty_rank() -> None:
    assert personalized_pagerank([("w", "p")], ["buyer-1"], SETTINGS) == {}


def test_entropy_is_highest_when_all_seeds_report_equally() -> None:
    even = counterparty_entropy({"b1": 2, "b2": 2, "b3": 2, "b4": 2}, seed_count=4)
    lopsided = counterparty_entropy({"b1": 7, "b2": 1}, seed_count=4)
    assert even == pytest.approx(1.0)
    assert lopsided < even


def test_entropy_is_zero_for_a_single_buyer_view() -> None:
    assert counterparty_entropy({"b1": 5}, seed_count=1) == 0.0


def test_sybil_ratio_counts_reports_without_paid_jobs() -> None:
    assert sybil_ratio(reports_received=0, paid_jobs=0) == 0.0
    assert sybil_ratio(reports_received=10, paid_jobs=10) == 0.0
    assert sybil_ratio(reports_received=20, paid_jobs=5) == pytest.approx(0.75)


def test_clique_score_is_share_of_reviewer_pairs_with_a_common_funder() -> None:
    funders = {
        "w1": frozenset({"root-a"}),
        "w2": frozenset({"root-a"}),
        "w3": frozenset({"root-b"}),
    }
    assert clique_score(funders, contaminated=False) == pytest.approx(1 / 3)


def test_clique_score_is_one_when_tied_to_a_quarantined_ring() -> None:
    assert clique_score({}, contaminated=True) == 1.0
