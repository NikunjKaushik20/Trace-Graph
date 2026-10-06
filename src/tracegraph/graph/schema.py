from typing import Any

from redis.exceptions import ResponseError

from tracegraph.graph.connection import GraphDatabase

LABELS_WITH_ID = (
    "Principal",
    "Buyer",
    "Writer",
    "Provider",
    "Wallet",
    "Root",
    "Task",
    "Job",
    "Decision",
    "Payment",
    "Claim",
    "Policy",
    "Ring",
    "Lesson",
)


# Creates the indexes and constraints a market graph needs, skipping ones that exist
async def apply_schema(database: GraphDatabase, graph_name: str, embedding_dimensions: int) -> None:
    graph = await database.select(graph_name)
    for label in LABELS_WITH_ID:
        await create_if_missing(graph.create_node_range_index(label, "id"))
        await create_if_missing(graph.create_node_unique_constraint(label, "id"))
    await create_if_missing(graph.create_node_range_index("Provider", "capability"))
    await create_if_missing(graph.create_edge_range_index("REPORTED", "t"))
    await create_if_missing(
        graph.create_node_vector_index(
            "Lesson", "embedding", dim=embedding_dimensions, similarity_function="cosine"
        )
    )


# Awaits a schema command and ignores the error FalkorDB gives when it already exists
async def create_if_missing(command: Any) -> None:
    try:
        await command
    except ResponseError as error:
        if "already" not in str(error).lower():
            raise
