from tracegraph.eval.contract import FROZEN_SETTINGS_HASH, MarketContract, settings_hash
from tracegraph.eval.outcomes import job_succeeds
from tracegraph.eval.population import RING_ROOT, build_market, funding_for

CONTRACT = MarketContract()


def test_scoreboard_settings_are_frozen() -> None:
    assert settings_hash(CONTRACT) == FROZEN_SETTINGS_HASH


def test_the_contract_matches_section_7_3_of_the_paper() -> None:
    assert (CONTRACT.providers, CONTRACT.malicious_share) == (1000, 0.30)
    assert (CONTRACT.buyers, CONTRACT.rounds, CONTRACT.delay_rounds) == (5, 60, 2)
    assert (CONTRACT.min_price_sats, CONTRACT.max_price_sats) == (5, 20)
    assert CONTRACT.seeds[0] == 1000 and CONTRACT.seeds[-1] == 1099


def test_every_lane_on_a_seed_sees_the_same_market() -> None:
    full, half = build_market(CONTRACT, 1000, 1.0), build_market(CONTRACT, 1000, 0.5)
    assert full.malicious == half.malicious and full.ring == half.ring
    assert full.prices == half.prices and full.outcome_draws == half.outcome_draws
    assert half.visible_sybils < full.visible_sybils == frozenset(full.sybil_ids)


def test_the_ring_is_thirty_malicious_providers_on_one_root() -> None:
    market = build_market(CONTRACT, 1001, 0.5)
    assert len(market.ring) == 30 and set(market.ring) <= market.malicious
    links = funding_for(market, market.buyer_ids, market.sybil_ids).links
    on_ring_root = {link.funded_id for link in links if link.funder_id == RING_ROOT}
    assert on_ring_root == set(market.ring) | market.visible_sybils


def test_honest_providers_fail_one_job_in_ten() -> None:
    market = build_market(CONTRACT, 1000, 1.0)
    honest = next(pid for pid in market.provider_ids if not market.is_malicious(pid))
    common = {"provider_id": honest, "price_sats": 20, "jobs_done": 9}
    assert not job_succeeds(CONTRACT, market, "strat", **common, draw=0.09)
    assert job_succeeds(CONTRACT, market, "strat", **common, draw=0.10)


def test_strat_defaults_on_half_the_expensive_jobs_and_calib_waits_two_jobs() -> None:
    market = build_market(CONTRACT, 1000, 1.0)
    bad = sorted(market.malicious)[0]
    expensive = {"provider_id": bad, "price_sats": 13, "draw": 0.3}
    cheap = {"provider_id": bad, "price_sats": 12, "draw": 0.3}
    assert not job_succeeds(CONTRACT, market, "strat", **expensive, jobs_done=0)
    assert job_succeeds(CONTRACT, market, "strat", **cheap, jobs_done=0)
    assert job_succeeds(CONTRACT, market, "calib", **expensive, jobs_done=1)
    assert not job_succeeds(CONTRACT, market, "calib", **expensive, jobs_done=2)
