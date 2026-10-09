from dataclasses import replace

from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.names import private_graph
from tracegraph.graph.schema import apply_schema
from tracegraph.graph.udf_loader import load_trace_udf
from tracegraph.market.graph_writes import (
    add_buyers,
    add_funding,
    add_providers,
    add_writers,
    record_settled_jobs,
)
from tracegraph.market.records import BuyerAccount
from tracegraph.market.roster import MarketSpec, demo_market, honest_market, ring_arrival


# Writes one market into one graph, on top of a fresh schema
async def write_market(
    database: GraphDatabase, graph_name: str, spec: MarketSpec, embedding_dimensions: int
) -> None:
    await apply_schema(database, graph_name, embedding_dimensions)
    await add_providers(database, graph_name, spec.providers)
    await add_buyers(database, graph_name, spec.buyers)
    await add_writers(database, graph_name, spec.writers)
    await add_funding(database, graph_name, spec.funding)
    await record_settled_jobs(database, graph_name, spec.history)


# The Alone view of one buyer: the same providers, but only that buyer and its own past jobs
def private_market(spec: MarketSpec, buyer_id: str) -> MarketSpec:
    return replace(
        spec,
        buyers=[buyer for buyer in spec.buyers if buyer.id == buyer_id],
        writers=[],
        history=[job for job in spec.history if job.payer_id == buyer_id],
    )


# Deletes the shared market graph and every buyer's private graph
async def delete_market_graphs(database: GraphDatabase, shared_graph: str) -> None:
    private_prefix = private_graph(shared_graph, "")
    for name in await database.list_graphs():
        if name == shared_graph or name.startswith(private_prefix):
            await database.delete_graph(name)


# Rebuilds the demo: the shared market, each buyer's private copy, and the Trace UDF
async def seed_demo_market(
    database: GraphDatabase,
    shared_graph: str,
    embedding_dimensions: int,
    now: float,
    *,
    with_ring: bool = True,
    with_udf: bool = True,
) -> MarketSpec:
    spec = demo_market(now) if with_ring else honest_market(now)
    await delete_market_graphs(database, shared_graph)
    await write_everywhere(database, shared_graph, spec, embedding_dimensions, spec.buyers)
    if with_udf:
        await load_trace_udf(database)
    return spec


# The ring shows up in a running demo: its listings everywhere, its fake reviews in the shared graph
async def add_ring(
    database: GraphDatabase, shared_graph: str, embedding_dimensions: int, now: float
) -> MarketSpec:
    spec = ring_arrival(now)
    buyers = honest_market(now).buyers
    await write_everywhere(database, shared_graph, spec, embedding_dimensions, buyers)
    return spec


# Writes a market piece to the shared graph and each buyer's private copy of it
async def write_everywhere(
    database: GraphDatabase,
    shared_graph: str,
    spec: MarketSpec,
    embedding_dimensions: int,
    buyers: list[BuyerAccount],
) -> None:
    await write_market(database, shared_graph, spec, embedding_dimensions)
    for buyer in buyers:
        own_view = private_market(spec, buyer.id)
        await write_market(
            database, private_graph(shared_graph, buyer.id), own_view, embedding_dimensions
        )
