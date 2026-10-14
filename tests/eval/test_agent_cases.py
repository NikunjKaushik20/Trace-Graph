import random
from collections import Counter
from typing import Any

import pytest

from tracegraph.eval.agent_cases import AgentCase, build_cases
from tracegraph.eval.case_market import case_market
from tracegraph.evidence.reader import ReportRow, assemble_evidence
from tracegraph.market.roster import MarketSpec
from tracegraph.trace.ranking import Ranking, rank_candidates
from tracegraph.trace.settings import TraceSettings

CASES = build_cases()


# Funders up to three hops above a node, from the case's funding links
def funders_of(spec: MarketSpec, node_id: str) -> frozenset[str]:
    parent = {link.funded_id: link.funder_id for link in spec.funding.links}
    found: list[str] = []
    while node_id in parent and len(found) < 3:
        node_id = parent[node_id]
        found.append(node_id)
    return frozenset(found)


# Reports as the guarded query returns them: outside writers are not admitted, so not counted
def report_rows(spec: MarketSpec, buyers: set[str]) -> list[ReportRow]:
    return [
        ReportRow(
            job.provider_id,
            job.payer_id,
            job.payer_id in buyers,
            job.ok,
            job.t,
            job.job_id,
            [],
            None if job.payer_id in buyers else "writer_not_admitted",
        )
        for job in spec.history
    ]


# Provider activity rows: every report in a case is backed by a paid job
def activity_rows(spec: MarketSpec) -> list[dict[str, Any]]:
    received = Counter(job.provider_id for job in spec.history)
    return [
        {
            "provider_id": listing.id,
            "price_sats": listing.price_sats,
            "reports_received": received[listing.id],
            "paid_jobs": received[listing.id],
            "quarantined": False,
            "contaminated": False,
        }
        for listing in spec.providers
    ]


# What trace_score would decide for buyer-1 on this case, under the closed-fleet guard
def ranking_for(case: AgentCase) -> Ranking:
    spec = case_market(case, now=0.0)
    buyers = {buyer.id for buyer in spec.buyers}
    funders = [
        {
            "provider_id": job.provider_id,
            "writer_id": job.payer_id,
            "funders": list(funders_of(spec, job.payer_id)),
        }
        for job in spec.history
    ]
    evidence = assemble_evidence(
        report_rows(spec, buyers), activity_rows(spec), funders, sorted(buyers)
    )
    return rank_candidates(
        evidence.evidence_by_provider,
        evidence.success_edges,
        evidence.seed_writers,
        TraceSettings(),
        random.Random(7),
    )


def test_there_are_100_cases_in_the_planned_mix() -> None:
    assert len(CASES) == 100
    assert Counter(case.label for case in CASES) == {"clean": 40, "suspicious": 30, "ring": 30}
    assert len({case.case_id for case in CASES}) == 100
    assert build_cases() == CASES


def test_ring_providers_are_the_cheapest_and_the_only_scammers() -> None:
    for case in CASES:
        honest = [p.price_sats for p in case.providers if p.provider_id not in case.malicious]
        scams = [p.price_sats for p in case.providers if p.provider_id in case.malicious]
        assert bool(scams) == (case.label == "ring")
        assert all(scam < min(honest) for scam in scams)


@pytest.mark.parametrize("case", [case for case in CASES if case.kind == "clean"])
def test_clean_cases_are_confident(case: AgentCase) -> None:
    assert ranking_for(case).status == "confident"


@pytest.mark.parametrize("case", [case for case in CASES if case.label == "suspicious"])
def test_suspicious_cases_are_flagged(case: AgentCase) -> None:
    ranking = ranking_for(case)
    assert ranking.status == "flagged"
    assert ranking.top is not None and ranking.top.provider_id not in case.malicious


@pytest.mark.parametrize("case", [case for case in CASES if case.kind == "ring"])
def test_ring_cases_flag_a_ring_provider_for_uncounted_praise(case: AgentCase) -> None:
    flags = ranking_for(case).flags
    flagged = [pid for pid, reasons in flags.items() if "reports_from_uncounted_writers" in reasons]
    assert flagged and set(flagged) <= case.malicious
