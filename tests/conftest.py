import os
import uuid
from collections.abc import AsyncIterator

import pytest

from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.schema import apply_schema

FALKORDB_URL = os.environ.get("FALKORDB_URL") or Settings().falkordb_url


# One connection for the whole test session, skipping database tests when FalkorDB is down
@pytest.fixture(scope="session")
async def database() -> AsyncIterator[GraphDatabase]:
    connection = GraphDatabase(FALKORDB_URL)
    if not await connection.is_reachable():
        pytest.skip("FalkorDB is not running")
    yield connection
    await connection.close()


# A fresh, empty graph with the schema applied, deleted after the test
@pytest.fixture
async def graph_name(database: GraphDatabase) -> AsyncIterator[str]:
    name = f"test:{uuid.uuid4().hex[:10]}"
    await apply_schema(database, name, embedding_dimensions=8)
    yield name
    await database.delete_graph(name)
