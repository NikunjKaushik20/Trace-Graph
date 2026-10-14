from tracegraph.evidence.reader import ReportRow
from tracegraph.evidence.scoring import ScoredCandidates
from tracegraph.evidence.what_if import ProviderShift, WhatIf, provider_shifts
from tracegraph.evidence.what_if_text import what_if_sentence
from tracegraph.trace.ranking import Ranking
from tracegraph.trace.utility import ProviderScore


# A provider score where only the id and utility matter
def score(provider_id: str, utility: float) -> ProviderScore:
    return ProviderScore(
        provider_id, utility, 0.5, 0.1, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1, 0, 0, None
    )


# A review of a provider, counted or ignored, with the funders its writer shares with it
def review(provider_id: str, writer_id: str, t: float, ignored: str | None) -> ReportRow:
    funders = ["root-ring-hub"] if writer_id.startswith("sybil") else []
    return ReportRow(provider_id, writer_id, False, True, t, f"job-{t}", funders, ignored)


# One scoring: providers in ranked order and the reviews it read
def scoring(utilities: list[tuple[str, float]], reports: list[ReportRow]) -> ScoredCandidates:
    ranking = Ranking([score(pid, value) for pid, value in utilities], [], {}, "flagged")
    return ScoredCandidates(ranking, reports, {}, "python", 1.0)


GUARDED = scoring(
    [("prov-summa", 0.27), ("prov-quickdigest", -0.28)],
    [
        review("prov-summa", "buyer-1", 1.0, None),
        review("prov-quickdigest", "sybil-01", 2.0, "writer_not_admitted"),
        review("prov-quickdigest", "sybil-02", 3.0, "writer_not_admitted"),
    ],
)
UNGUARDED_REPORTS = [
    review("prov-summa", "buyer-1", 1.0, None),
    review("prov-quickdigest", "sybil-01", 2.0, None),
    review("prov-quickdigest", "sybil-02", 3.0, None),
]


def test_a_provider_that_gains_reviews_but_not_the_top_spot_is_reported_as_a_shift() -> None:
    unguarded = scoring([("prov-summa", 0.27), ("prov-quickdigest", 0.08)], UNGUARDED_REPORTS)
    [shift] = provider_shifts(GUARDED, unguarded)
    assert shift.provider_id == "prov-quickdigest"
    assert shift.reports_counted_now == 2
    assert shift.writers == ["sybil-01", "sybil-02"]
    assert shift.shared_funders == ["root-ring-hub"]
    assert (shift.position_before, shift.position_after) == (2, 2)


def test_a_flip_is_reported_with_the_new_top_pick() -> None:
    unguarded = scoring([("prov-quickdigest", 0.40), ("prov-summa", 0.27)], UNGUARDED_REPORTS)
    shifts = provider_shifts(GUARDED, unguarded)
    assert [shift.provider_id for shift in shifts] == ["prov-quickdigest", "prov-summa"]
    assert shifts[1].reports_counted_now == 0
    assert shifts[1].position_after == 2


def test_the_sentence_says_the_pick_held_and_who_moved() -> None:
    shift = ProviderShift(
        "prov-quickdigest", -0.28, 0.08, 2, 2, 20, ["sybil-01"], ["root-ring-hub"], ["policy-1"]
    )
    result = WhatIf("dec-1", "closed", "unguarded", "prov-summa", "prov-summa", True, [shift], 2.0)
    assert what_if_sentence(result) == (
        "With the guard off, TRACE would still rank prov-summa first, so the guard did not "
        "change this pick. prov-quickdigest would count 20 more reports from writers that share "
        "funders with it (root-ring-hub), moving its score from -0.28 to 0.08. It has since been "
        "quarantined (policy-1)."
    )


def test_the_sentence_names_the_new_pick_and_warns_when_the_replay_is_off() -> None:
    shift = ProviderShift("prov-quickdigest", -0.28, 0.40, 2, 1, 3, ["writer-07"], [], [], 0, 1)
    result = WhatIf(
        "dec-1", "closed", "open", "prov-summa", "prov-quickdigest", False, [shift], 2.0
    )
    sentence = what_if_sentence(result)
    assert sentence.startswith(
        "With outside reports counted unless the money links them, TRACE would have ranked "
        "prov-quickdigest first instead of prov-summa."
    )
    assert "from writers outside the fleet" in sentence
    assert "Since then, 1 of its 1 paid jobs failed." in sentence
    assert sentence.endswith("so read this as approximate.")
