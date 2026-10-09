from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.market_setup import (
    CREATE_BUYERS,
    CREATE_PROVIDERS,
    CREATE_ROOTS,
    CREATE_WALLETS,
    CREATE_WRITERS,
    LINK_FUNDING,
)
from tracegraph.graph.queries.outcomes import RECORD_SETTLED_JOBS, RECORD_UNPAID_REPORTS
from tracegraph.market.records import (
    BuyerAccount,
    FundingChains,
    ProviderListing,
    SettledJob,
    UnpaidReport,
    as_rows,
)


# Adds providers to a market graph
async def add_providers(
    database: GraphDatabase, graph_name: str, providers: list[ProviderListing]
) -> None:
    await database.run(graph_name, CREATE_PROVIDERS, {"providers": as_rows(providers)})


# Adds buyers, and the principals that own them, to a market graph
async def add_buyers(database: GraphDatabase, graph_name: str, buyers: list[BuyerAccount]) -> None:
    await database.run(graph_name, CREATE_BUYERS, {"buyers": as_rows(buyers)})


# Adds outside writer identities to a market graph
async def add_writers(database: GraphDatabase, graph_name: str, writer_ids: list[str]) -> None:
    rows = [{"id": writer_id} for writer_id in writer_ids]
    await database.run(graph_name, CREATE_WRITERS, {"writers": rows})


# Adds funding roots, wallets and the FUNDED_BY links between them
async def add_funding(database: GraphDatabase, graph_name: str, chains: FundingChains) -> None:
    await database.run(graph_name, CREATE_ROOTS, {"root_ids": chains.root_ids})
    await database.run(graph_name, CREATE_WALLETS, {"wallet_ids": chains.wallet_ids})
    await database.run(graph_name, LINK_FUNDING, {"links": as_rows(chains.links)})


# Writes a batch of finished jobs with their payments and outcome reports
async def record_settled_jobs(
    database: GraphDatabase,
    graph_name: str,
    jobs: list[SettledJob],
    timer: GraphTimer | None = None,
) -> None:
    if jobs:
        await database.run(graph_name, RECORD_SETTLED_JOBS, {"jobs": as_rows(jobs)}, timer)


# Writes reports that no paid job backs
async def record_unpaid_reports(
    database: GraphDatabase,
    graph_name: str,
    reports: list[UnpaidReport],
    timer: GraphTimer | None = None,
) -> None:
    if reports:
        await database.run(graph_name, RECORD_UNPAID_REPORTS, {"reports": as_rows(reports)}, timer)
