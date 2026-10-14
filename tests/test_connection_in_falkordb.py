import uuid

import pytest

from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.ops import READ_SPEND
from tracegraph.llm.spend import Prices, SpendMeter

pytestmark = pytest.mark.falkordb


async def test_reading_a_graph_that_does_not_exist_yet_gives_no_rows(
    database: GraphDatabase,
) -> None:
    never_written = f"test-missing:{uuid.uuid4().hex[:8]}"
    assert await database.rows(never_written, READ_SPEND) == []
    assert never_written not in await database.list_graphs()


async def test_a_fresh_deployment_has_spent_nothing(database: GraphDatabase) -> None:
    meter = SpendMeter(
        database, f"test-ops:{uuid.uuid4().hex[:8]}", Prices(0.15, 0.075, 0.60), limit_usd=1.80
    )
    report = await meter.report()
    assert report.usd == 0.0
    assert report.calls == 0
