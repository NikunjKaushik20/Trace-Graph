import random
from dataclasses import dataclass

from tracegraph.eval.contract import MarketContract
from tracegraph.graph.connection import GraphDatabase
from tracegraph.market.graph_writes import add_buyers, add_funding, add_providers, add_writers
from tracegraph.market.records import BuyerAccount, FundingChains, FundingLink, ProviderListing

RING_ROOT = "root-ring"


@dataclass(frozen=True)
class SimMarket:
    provider_ids: list[str]
    malicious: frozenset[str]
    ring: list[str]
    buyer_ids: list[str]
    sybil_ids: list[str]
    visible_sybils: frozenset[str]
    prices: list[list[int]]
    outcome_draws: list[list[float]]

    # Whether a provider is one of the 30% that default on purpose
    def is_malicious(self, provider_id: str) -> bool:
        return provider_id in self.malicious


# Draws one seed's market; every lane on that seed gets the same providers, prices and draws
def build_market(contract: MarketContract, seed: int, funding_visible: float) -> SimMarket:
    market_rng = random.Random(f"{seed}:market")
    provider_ids = [f"prov-{index:04d}" for index in range(contract.providers)]
    malicious = [pid for pid in provider_ids if market_rng.random() < contract.malicious_share]
    ring = sorted(market_rng.sample(malicious, contract.ring_providers))
    sybil_rng = random.Random(f"{seed}:sybils")
    sybil_ids = [f"sybil-{index:02d}" for index in range(contract.sybil_writers)]
    visible = frozenset(sid for sid in sybil_ids if sybil_rng.random() < funding_visible)
    prices, draws = job_draws(contract, seed)
    return SimMarket(
        provider_ids=provider_ids,
        malicious=frozenset(malicious),
        ring=ring,
        buyer_ids=[f"buyer-{index + 1}" for index in range(contract.buyers)],
        sybil_ids=sybil_ids,
        visible_sybils=visible,
        prices=prices,
        outcome_draws=draws,
    )


# Each round's job price and outcome draw for each buyer
def job_draws(contract: MarketContract, seed: int) -> tuple[list[list[int]], list[list[float]]]:
    job_rng = random.Random(f"{seed}:jobs")
    prices: list[list[int]] = []
    draws: list[list[float]] = []
    for _ in range(contract.rounds):
        low, high = contract.min_price_sats, contract.max_price_sats
        prices.append([job_rng.randint(low, high) for _ in range(contract.buyers)])
        draws.append([job_rng.random() for _ in range(contract.buyers)])
    return prices, draws


# Writes the providers, buyers, Sybils and funding of one market graph
async def write_market(
    database: GraphDatabase,
    graph_name: str,
    market: SimMarket,
    buyer_ids: list[str],
    with_sybils: bool,
) -> None:
    listings = [ProviderListing(pid, pid, "summarise", None) for pid in market.provider_ids]
    await add_providers(database, graph_name, listings)
    accounts = [BuyerAccount(bid, bid, True, 1_000_000) for bid in buyer_ids]
    await add_buyers(database, graph_name, accounts)
    sybil_ids = market.sybil_ids if with_sybils else []
    await add_writers(database, graph_name, sybil_ids)
    await add_funding(database, graph_name, funding_for(market, buyer_ids, sybil_ids))


# Each buyer has its own root; the ring and the Sybils that do not hide it share the ring's root
def funding_for(market: SimMarket, buyer_ids: list[str], sybil_ids: list[str]) -> FundingChains:
    links = [FundingLink(bid, f"root-{bid}") for bid in buyer_ids]
    links += [FundingLink(pid, RING_ROOT) for pid in market.ring]
    for sybil_id in sybil_ids:
        funder = RING_ROOT if sybil_id in market.visible_sybils else f"root-{sybil_id}"
        links.append(FundingLink(sybil_id, funder))
    roots = sorted({link.funder_id for link in links})
    return FundingChains(root_ids=roots, wallet_ids=[], links=links)
