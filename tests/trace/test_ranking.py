import random

from tracegraph.trace.ranking import rank_candidates
from tracegraph.trace.settings import TraceSettings
from tracegraph.trace.utility import ProviderEvidence

SETTINGS = TraceSettings()


# Builds evidence for a provider whose reports all come from one buyer's paid jobs
def evidence(
    provider_id: str, outcomes: list[bool], quarantined: bool = False, ignored_claims: int = 0
) -> ProviderEvidence:
    successes = sum(outcomes)
    return ProviderEvidence(
        provider_id=provider_id,
        outcomes=outcomes,
        success_counts_by_writer={"buyer-1": successes} if successes else {},
        reports_received=len(outcomes),
        paid_jobs=len(outcomes),
        ignored_claims=ignored_claims,
        quarantined=quarantined,
    )


def test_proven_provider_beats_a_newcomer() -> None:
    candidates = {
        "p-proven": evidence("p-proven", [True] * 12),
        "p-new": evidence("p-new", []),
    }
    ranking = rank_candidates(
        candidates, [("buyer-1", "p-proven")], ["buyer-1"], SETTINGS, random.Random(1)
    )
    assert ranking.top is not None
    assert ranking.top.provider_id == "p-proven"


def test_two_proven_providers_with_a_clear_gap_give_a_confident_decision() -> None:
    candidates = {
        "p-strong": evidence("p-strong", [True] * 30),
        "p-decent": evidence("p-decent", [True] * 6),
    }
    edges = [("buyer-1", "p-strong"), ("buyer-1", "p-decent")]
    ranking = rank_candidates(candidates, edges, ["buyer-1"], SETTINGS, random.Random(1))
    assert ranking.status == "confident"
    assert ranking.flags == {}


def test_quarantined_and_failing_providers_are_excluded() -> None:
    candidates = {
        "p-ok": evidence("p-ok", [True] * 5),
        "p-ring": evidence("p-ring", [True] * 20, quarantined=True),
        "p-bad": evidence("p-bad", [True, False] * 8),
    }
    ranking = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(1))
    assert [score.provider_id for score in ranking.ranked] == ["p-ok"]
    reasons = {score.provider_id: score.excluded_because for score in ranking.excluded}
    assert reasons["p-ring"] == "quarantined"
    assert reasons["p-bad"] in {"cusum_alarm", "fails_more_than_honest"}


def test_uncounted_praise_flags_the_decision() -> None:
    candidates = {"p-ring": evidence("p-ring", [True] * 4, ignored_claims=20)}
    ranking = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(1))
    assert ranking.status == "flagged"
    assert "reports_from_uncounted_writers" in ranking.flags["p-ring"]


def test_no_eligible_provider_when_everyone_is_excluded() -> None:
    candidates = {"p-ring": evidence("p-ring", [], quarantined=True)}
    ranking = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(1))
    assert ranking.status == "no_eligible_provider"
    assert ranking.top is None


def test_ties_are_broken_by_the_seeded_random_source() -> None:
    candidates = {f"p-{index}": evidence(f"p-{index}", []) for index in range(20)}
    first = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(7))
    second = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(7))
    assert first.top is not None and second.top is not None
    assert first.top.provider_id == second.top.provider_id


def test_a_suspicious_runner_up_flags_the_decision_but_not_the_top_pick() -> None:
    candidates = {
        "p-proven": evidence("p-proven", [True] * 12),
        "p-ring": evidence("p-ring", [], ignored_claims=20),
    }
    ranking = rank_candidates(
        candidates, [("buyer-1", "p-proven")], ["buyer-1"], SETTINGS, random.Random(1)
    )
    assert ranking.top is not None and ranking.top.provider_id == "p-proven"
    assert ranking.status == "flagged"
    assert "p-proven" not in ranking.flags
    assert ranking.flags["p-ring"] == ["new_provider", "reports_from_uncounted_writers"]
    assert ranking.flag_lines == [
        "p-ring: new_provider",
        "p-ring: reports_from_uncounted_writers",
    ]


def test_providers_below_the_hireable_set_do_not_raise_flags() -> None:
    candidates = {f"p-{index}": evidence(f"p-{index}", [True] * (20 - index)) for index in range(3)}
    candidates["p-new"] = evidence("p-new", [])
    ranking = rank_candidates(candidates, [], ["buyer-1"], SETTINGS, random.Random(1))
    assert ranking.ranked[-1].provider_id == "p-new"
    assert "p-new" not in ranking.flags
