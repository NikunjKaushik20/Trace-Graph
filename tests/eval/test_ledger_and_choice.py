import random
from typing import Any

from tracegraph.eval.choosing import pick_greedy, provider_to_investigate, score_view
from tracegraph.eval.ledger import EvidenceLedger
from tracegraph.eval.summary import percentile
from tracegraph.trace.settings import TraceSettings

SETTINGS = TraceSettings()


# One guarded report row as the round read returns it
def report(
    writer: str, provider: str, ok: bool, t: int, ignored: str | None = None
) -> dict[str, Any]:
    return {
        "provider_id": provider,
        "writer_id": writer,
        "admitted": writer.startswith("buyer"),
        "ok": ok,
        "t": t,
        "job_id": f"j{t}-{writer}",
        "shared_funders": [],
        "ignored_because": ignored,
        "writer_funders": [],
    }


def test_own_reports_count_at_once_and_others_after_two_rounds() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1", "buyer-2"], delay_rounds=2)
    ledger.add_round([report("buyer-1", "prov-a", True, 0)])
    ledger.advance_to(1)
    assert ledger.view_for("buyer-1").evidence["prov-a"].outcomes == [True]
    assert ledger.view_for("buyer-2").evidence["prov-a"].outcomes == []
    ledger.advance_to(2)
    assert ledger.view_for("buyer-2").evidence["prov-a"].outcomes == [True]


def test_activity_counts_at_once_but_ignored_claims_wait_for_the_delay() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=2)
    ledger.add_round([report("sybil-01", "prov-r", True, 0, "shares_funding_with_provider")])
    ledger.advance_to(1)
    assert ledger.shared["prov-r"].reports_received == 1
    assert ledger.shared["prov-r"].ignored_claims == 0
    ledger.advance_to(2)
    assert ledger.shared["prov-r"].ignored_claims == 1
    assert ledger.ignored_writers["prov-r"] == ["sybil-01"]
    assert ledger.shared["prov-r"].outcomes == []


def test_a_buyers_own_view_leaves_the_shared_evidence_alone() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=2)
    ledger.add_round([report("buyer-1", "prov-a", False, 0)])
    ledger.advance_to(1)
    ledger.view_for("buyer-1")
    assert ledger.shared["prov-a"].outcomes == []


def test_a_proven_provider_beats_the_unseen_ones() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=2)
    ledger.add_round([report("buyer-1", "prov-a", True, t) for t in range(3)])
    ledger.advance_to(3)
    scored = score_view(ledger.view_for("buyer-1"), ["prov-a", "prov-b"], SETTINGS)
    assert pick_greedy(scored, random.Random(1)) == "prov-a"


def test_ties_are_broken_at_random_among_unseen_providers() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=2)
    scored = score_view(ledger.view_for("buyer-1"), ["prov-a", "prov-b", "prov-c"], SETTINGS)
    picks = {pick_greedy(scored, random.Random(seed)) for seed in range(30)}
    assert picks == {"prov-a", "prov-b", "prov-c"}


def test_an_empty_market_has_nobody_to_pick() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=2)
    scored = score_view(ledger.view_for("buyer-1"), [], SETTINGS)
    assert pick_greedy(scored, random.Random(1)) is None


def test_only_providers_praised_by_uncounted_writers_are_investigated() -> None:
    ledger = EvidenceLedger(seed_writers=["buyer-1"], delay_rounds=0)
    rows = [report("buyer-1", "prov-r", True, t) for t in range(3)]
    ignored = "shares_funding_with_provider"
    rows += [report(f"sybil-0{n}", "prov-r", True, 0, ignored) for n in range(3)]
    ledger.add_round(rows)
    ledger.advance_to(3)
    scored = score_view(ledger.view_for("buyer-1"), ["prov-r", "prov-x"], SETTINGS)
    assert provider_to_investigate(scored, SETTINGS, set()) == "prov-r"
    assert provider_to_investigate(scored, SETTINGS, {"prov-r"}) is None


def test_percentile_matches_linear_interpolation() -> None:
    values = [float(value) for value in range(1, 11)]
    assert percentile(values, 0.9) == 9.1
    assert percentile(values, 0.5) == 5.5
