from tracegraph.graph.connection import GraphDatabase
from tracegraph.market.graph_writes import (
    add_buyers,
    add_funding,
    add_providers,
    add_writers,
    record_settled_jobs,
)
from tracegraph.market.records import (
    BuyerAccount,
    FundingChains,
    FundingLink,
    ProviderListing,
    SettledJob,
)

SMALL_FUNDING = FundingChains(
    root_ids=["root-good", "root-attacker"],
    wallet_ids=["wallet-ring"],
    links=[
        FundingLink("p-good", "root-good"),
        FundingLink("wallet-ring", "root-attacker"),
        FundingLink("p-ring", "wallet-ring"),
        FundingLink("sybil-1", "wallet-ring"),
        FundingLink("sybil-2", "root-attacker"),
    ],
)


# Two honest buyers, one honest provider, and a ring provider praised by two Sybils it funds
async def build_small_market(database: GraphDatabase, graph_name: str) -> None:
    await add_providers(
        database,
        graph_name,
        [
            ProviderListing("p-good", "Good", "summarise", 12),
            ProviderListing("p-ring", "Ring", "summarise", 6),
        ],
    )
    await add_buyers(
        database,
        graph_name,
        [
            BuyerAccount("buyer-1", "Buyer 1", admitted=True, balance_sats=500),
            BuyerAccount("buyer-2", "Buyer 2", admitted=True, balance_sats=500),
        ],
    )
    await add_writers(database, graph_name, ["sybil-1", "sybil-2"])
    await add_funding(database, graph_name, SMALL_FUNDING)
    await record_settled_jobs(
        database,
        graph_name,
        [
            SettledJob("j1", "pay1", "buyer-1", "p-good", 12, ok=True, t=1),
            SettledJob("j2", "pay2", "sybil-1", "p-ring", 6, ok=True, t=1),
            SettledJob("j3", "pay3", "sybil-2", "p-ring", 6, ok=True, t=2),
        ],
    )
