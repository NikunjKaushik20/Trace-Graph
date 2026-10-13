from tracegraph.eval.agent_cases import AgentCase, CaseProvider
from tracegraph.market.records import (
    BuyerAccount,
    FundingChains,
    FundingLink,
    ProviderListing,
    SettledJob,
)
from tracegraph.market.roster import MarketSpec

AGENT_BUYER = "buyer-1"
HISTORY_BUYERS = ["buyer-2", "buyer-3", "buyer-4", "buyer-5"]
HUB, OPS_WALLET, PROMO_WALLET = "root-hub", "wallet-ops", "wallet-promo"


# One case as a market: listings, buyers, outside writers, funding and past jobs
def case_market(case: AgentCase, now: float) -> MarketSpec:
    writers = writer_ids(case)
    providers = [
        ProviderListing(
            p.provider_id, p.provider_id.removeprefix("prov-").title(), "summarise", p.price_sats
        )
        for p in case.providers
    ]
    buyers = [BuyerAccount(bid, bid, True, 1000) for bid in [AGENT_BUYER, *HISTORY_BUYERS]]
    history: list[SettledJob] = []
    for provider in case.providers:
        history += buyer_history(provider, now) + outside_praise(provider, writers, now)
    behaviours = {p.provider_id: p.behaviour for p in case.providers}
    return MarketSpec(providers, behaviours, buyers, writers, case_funding(case, writers), history)


# Outside writers: enough for the provider with the most outside praise
def writer_ids(case: AgentCase) -> list[str]:
    needed = max((min(p.outside_praise, 8) for p in case.providers), default=0)
    return [f"writer-{index:02d}" for index in range(1, needed + 1)]


# Past jobs by the other admitted buyers, taken in turn
def buyer_history(provider: CaseProvider, now: float) -> list[SettledJob]:
    jobs = []
    for index, mark in enumerate(provider.history):
        job_id = f"job-past-{provider.provider_id}-{index}"
        t = now - 600.0 * (len(provider.history) - index)
        buyer = HISTORY_BUYERS[index % len(HISTORY_BUYERS)]
        jobs.append(
            SettledJob(
                job_id,
                f"pay-{job_id}",
                buyer,
                provider.provider_id,
                provider.price_sats,
                mark == "o",
                t,
            )
        )
    return jobs


# Paid five-star jobs from outside writers
def outside_praise(provider: CaseProvider, writers: list[str], now: float) -> list[SettledJob]:
    jobs = []
    for index in range(provider.outside_praise):
        job_id = f"job-praise-{provider.provider_id}-{index}"
        writer = writers[index % len(writers)]
        t = now - 60.0 * (provider.outside_praise - index)
        jobs.append(
            SettledJob(
                job_id, f"pay-{job_id}", writer, provider.provider_id, provider.price_sats, True, t
            )
        )
    return jobs


# Everyone has their own root, except the ring: its providers and writers trace back to one hub
def case_funding(case: AgentCase, writers: list[str]) -> FundingChains:
    has_ring = any(p.in_ring for p in case.providers)
    links = [FundingLink(bid, f"root-{bid}") for bid in [AGENT_BUYER, *HISTORY_BUYERS]]
    for provider in case.providers:
        funder = OPS_WALLET if provider.in_ring else f"root-{provider.provider_id}"
        links.append(FundingLink(provider.provider_id, funder))
    for writer in writers:
        links.append(FundingLink(writer, PROMO_WALLET if has_ring else f"root-{writer}"))
    wallets = [OPS_WALLET, PROMO_WALLET] if has_ring else []
    if has_ring:
        links += [FundingLink(OPS_WALLET, HUB), FundingLink(PROMO_WALLET, HUB)]
    roots = sorted({link.funder_id for link in links} - set(wallets))
    return FundingChains(root_ids=roots, wallet_ids=wallets, links=links)
