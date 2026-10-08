from dataclasses import dataclass

from tracegraph.market.providers import Behaviour
from tracegraph.market.records import (
    BuyerAccount,
    FundingChains,
    FundingLink,
    ProviderListing,
    SettledJob,
)
from tracegraph.market.work import Capability


@dataclass(frozen=True)
class DemoProvider:
    id: str
    name: str
    capability: Capability
    price_sats: int
    behaviour: Behaviour
    history: str = ""
    in_ring: bool = False


@dataclass(frozen=True)
class MarketSpec:
    providers: list[ProviderListing]
    behaviours: dict[str, Behaviour]
    buyers: list[BuyerAccount]
    writers: list[str]
    funding: FundingChains
    history: list[SettledJob]


DEMO_PROVIDERS = [
    DemoProvider("prov-summa", "Summa", "summarise", 12, "honest", "ooooooooxo"),
    DemoProvider("prov-brevity", "Brevity Labs", "summarise", 15, "honest", "oooooo"),
    DemoProvider("prov-quickdigest", "QuickDigest", "summarise", 6, "scam", in_ring=True),
    DemoProvider("prov-tldr-pro", "TLDR Pro", "summarise", 14, "strategic", "ooxoxxox"),
    DemoProvider("prov-keyword-co", "Keyword Co", "extract_keywords", 10, "honest", "oooooooo"),
    DemoProvider("prov-tagsmith", "Tagsmith", "extract_keywords", 13, "honest", "ooooxoo"),
    DemoProvider("prov-tagstar", "TagStar", "extract_keywords", 5, "scam", in_ring=True),
    DemoProvider("prov-cheaptags", "CheapTags", "extract_keywords", 8, "scam", "oxx"),
    DemoProvider("prov-lingua", "Lingua", "translate", 11, "honest", "ooooooooo"),
    DemoProvider("prov-polyglot", "Polyglot", "translate", 16, "honest", "oooo"),
    DemoProvider("prov-transfast", "TransFast", "translate", 7, "scam", in_ring=True),
    DemoProvider("prov-wordbridge", "WordBridge", "translate", 15, "strategic", "oooooooxx"),
]

PRINCIPALS = {
    "principal-acme": ("Acme Research", ["buyer-1", "buyer-2"]),
    "principal-northwind": ("Northwind Media", ["buyer-3", "buyer-4"]),
    "principal-globex": ("Globex", ["buyer-5"]),
}

SYBIL_WRITERS = [f"sybil-{index:02d}" for index in range(1, 9)]
FAKE_REVIEWS_PER_RING_PROVIDER = 20
STARTING_BALANCE_SATS = 1000
HISTORY_SPACING_SECONDS = 600.0


# The demo market: who sells what, who buys, who funds whom, and what already happened
def demo_market(now: float) -> MarketSpec:
    return combine(honest_market(now), ring_arrival(now))


# Everything except the ring: the market as it is before the scammers show up
def honest_market(now: float) -> MarketSpec:
    honest = [p for p in DEMO_PROVIDERS if not p.in_ring]
    buyers = [
        BuyerAccount(buyer_id, f"Buyer {buyer_id[-1]}", True, STARTING_BALANCE_SATS, pid, name)
        for pid, (name, buyer_ids) in PRINCIPALS.items()
        for buyer_id in buyer_ids
    ]
    return MarketSpec(
        providers=[listing_for(p) for p in honest],
        behaviours={p.id: p.behaviour for p in honest},
        buyers=buyers,
        writers=[],
        funding=honest_funding(honest),
        history=honest_history(now, honest, [buyer.id for buyer in buyers]),
    )


# The ring arriving: cheap scammers, the Sybils that praise them, and the money behind both
def ring_arrival(now: float) -> MarketSpec:
    ring = [p for p in DEMO_PROVIDERS if p.in_ring]
    return MarketSpec(
        providers=[listing_for(p) for p in ring],
        behaviours={p.id: p.behaviour for p in ring},
        buyers=[],
        writers=list(SYBIL_WRITERS),
        funding=ring_funding(ring),
        history=fake_ring_reviews(now),
    )


# Two market pieces written as one
def combine(first: MarketSpec, second: MarketSpec) -> MarketSpec:
    return MarketSpec(
        providers=first.providers + second.providers,
        behaviours={**first.behaviours, **second.behaviours},
        buyers=first.buyers + second.buyers,
        writers=first.writers + second.writers,
        funding=FundingChains(
            root_ids=first.funding.root_ids + second.funding.root_ids,
            wallet_ids=first.funding.wallet_ids + second.funding.wallet_ids,
            links=first.funding.links + second.funding.links,
        ),
        history=first.history + second.history,
    )


# A provider's public listing
def listing_for(provider: DemoProvider) -> ProviderListing:
    return ProviderListing(provider.id, provider.name, provider.capability, provider.price_sats)


# Past jobs from admitted buyers, taken in turn, with "o" a success and "x" a failure
def honest_history(
    now: float, providers: list[DemoProvider], buyer_ids: list[str]
) -> list[SettledJob]:
    jobs = []
    for provider in providers:
        for index, mark in enumerate(provider.history):
            t = now - HISTORY_SPACING_SECONDS * (len(provider.history) - index)
            job_id = f"job-past-{provider.id}-{index}"
            buyer_id = buyer_ids[index % len(buyer_ids)]
            jobs.append(
                SettledJob(
                    job_id,
                    f"pay-{job_id}",
                    buyer_id,
                    provider.id,
                    provider.price_sats,
                    mark == "o",
                    t,
                )
            )
    return jobs


# Paid self-jobs by the Sybil writers: fresh five-star reviews for every ring provider
def fake_ring_reviews(now: float) -> list[SettledJob]:
    jobs = []
    ring = [provider for provider in DEMO_PROVIDERS if provider.in_ring]
    for provider in ring:
        for index in range(FAKE_REVIEWS_PER_RING_PROVIDER):
            writer = SYBIL_WRITERS[index % len(SYBIL_WRITERS)]
            job_id = f"job-sybil-{provider.id}-{index}"
            t = now - 60.0 * (FAKE_REVIEWS_PER_RING_PROVIDER - index)
            jobs.append(
                SettledJob(
                    job_id, f"pay-{job_id}", writer, provider.id, provider.price_sats, True, t
                )
            )
    return jobs


# Each honest buyer and provider has its own root
def honest_funding(honest: list[DemoProvider]) -> FundingChains:
    roots = [f"root-{pid.removeprefix('principal-')}" for pid in PRINCIPALS]
    links = [
        FundingLink(buyer_id, f"root-{pid.removeprefix('principal-')}")
        for pid, (_, buyer_ids) in PRINCIPALS.items()
        for buyer_id in buyer_ids
    ]
    for provider in honest:
        roots.append(f"root-{provider.id}")
        links.append(FundingLink(provider.id, f"root-{provider.id}"))
    return FundingChains(root_ids=roots, wallet_ids=[], links=links)


# The ring hides one hub behind wallets: providers on one side, the Sybils on the other
def ring_funding(ring: list[DemoProvider]) -> FundingChains:
    links = [FundingLink(provider.id, "wallet-ring-ops") for provider in ring]
    links += [
        FundingLink("wallet-ring-ops", "root-ring-hub"),
        FundingLink("wallet-ring-promo", "root-ring-hub"),
        FundingLink("wallet-ring-promo-2", "wallet-ring-promo"),
    ]
    links += [FundingLink(writer, "wallet-ring-promo-2") for writer in SYBIL_WRITERS]
    wallets = ["wallet-ring-ops", "wallet-ring-promo", "wallet-ring-promo-2"]
    return FundingChains(root_ids=["root-ring-hub"], wallet_ids=wallets, links=links)
