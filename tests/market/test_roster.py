from tracegraph.market.records import FundingLink
from tracegraph.market.roster import DEMO_PROVIDERS, SYBIL_WRITERS, demo_market


# Every funder reachable from a node in 1 to 3 FUNDED_BY hops, like the guard query
def funders_within_three_hops(node: str, links: list[FundingLink]) -> set[str]:
    reached: set[str] = set()
    frontier = {node}
    for _ in range(3):
        frontier = {link.funder_id for link in links if link.funded_id in frontier}
        reached |= frontier
    return reached


def test_every_sybil_shares_a_funder_with_every_ring_provider_within_three_hops() -> None:
    links = demo_market(now=0).funding.links
    ring = [provider.id for provider in DEMO_PROVIDERS if provider.in_ring]
    for writer in SYBIL_WRITERS:
        writer_funders = funders_within_three_hops(writer, links)
        for provider in ring:
            assert writer_funders & funders_within_three_hops(provider, links)


def test_sybils_share_no_funder_with_honest_providers_or_buyers() -> None:
    spec = demo_market(now=0)
    links = spec.funding.links
    sybil_funders = funders_within_three_hops(SYBIL_WRITERS[0], links)
    outsiders = [p.id for p in DEMO_PROVIDERS if not p.in_ring] + [b.id for b in spec.buyers]
    for node in outsiders:
        assert not sybil_funders & funders_within_three_hops(node, links)


def test_ring_providers_have_only_sybil_reviews() -> None:
    spec = demo_market(now=1000.0)
    ring = {provider.id for provider in DEMO_PROVIDERS if provider.in_ring}
    ring_jobs = [job for job in spec.history if job.provider_id in ring]
    assert {job.payer_id for job in ring_jobs} <= set(SYBIL_WRITERS)
    assert all(job.ok for job in ring_jobs)
    assert all(job.t < 1000.0 for job in spec.history)


def test_job_ids_are_unique() -> None:
    history = demo_market(now=0).history
    assert len({job.job_id for job in history}) == len(history)
