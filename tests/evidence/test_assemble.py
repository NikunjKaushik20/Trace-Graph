from tracegraph.evidence.reader import ReportRow, assemble_evidence


# Builds a report row with the fields these tests care about
def report(
    provider_id: str, writer_id: str, ok: bool, t: float, ignored_because: str | None = None
) -> ReportRow:
    return ReportRow(
        provider_id=provider_id,
        writer_id=writer_id,
        admitted=ignored_because is None,
        ok=ok,
        t=t,
        job_id=None,
        shared_funders=[],
        ignored_because=ignored_because,
    )


# Builds an activity row for one provider
def activity(provider_id: str, reports_received: int = 0, paid_jobs: int = 0) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "capability": "summarise",
        "price_sats": 10,
        "reports_received": reports_received,
        "paid_jobs": paid_jobs,
        "quarantined": False,
        "contaminated": False,
    }


def test_counted_reports_become_outcomes_and_ignored_ones_become_claims() -> None:
    reports = [
        report("p1", "buyer-1", ok=True, t=1),
        report("p1", "buyer-2", ok=False, t=2),
        report("p1", "sybil-1", ok=True, t=3, ignored_because="writer_not_admitted"),
    ]
    candidates = assemble_evidence(reports, [activity("p1", 3, 2)], [], ["buyer-1", "buyer-2"])
    evidence = candidates.evidence_by_provider["p1"]
    assert evidence.outcomes == [True, False]
    assert evidence.ignored_claims == 1
    assert evidence.success_counts_by_writer == {"buyer-1": 1}
    assert candidates.success_edges == [("buyer-1", "p1")]


def test_providers_without_reports_are_still_candidates() -> None:
    candidates = assemble_evidence([], [activity("p-new")], [], ["buyer-1"])
    assert candidates.evidence_by_provider["p-new"].outcomes == []
    assert candidates.prices == {"p-new": 10}


def test_reviewer_funders_are_attached_to_the_provider_they_rated() -> None:
    funders = [{"provider_id": "p1", "writer_id": "sybil-1", "funders": ["root-x"]}]
    candidates = assemble_evidence([], [activity("p1")], funders, [])
    assert candidates.evidence_by_provider["p1"].reviewer_funders == {
        "sybil-1": frozenset({"root-x"})
    }
