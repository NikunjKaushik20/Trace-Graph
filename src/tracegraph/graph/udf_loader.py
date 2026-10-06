from pathlib import Path
from typing import Any

from redis.exceptions import ResponseError

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.query import Query

TRACE_LIBRARY = "Trace"
TRACE_SCRIPT = Path(__file__).parent / "udf" / "trace_score.js"
UNKNOWN_TRACE_FUNCTION = "Unknown function 'Trace."


class UdfRejectedError(RuntimeError):
    pass


# Reads the JavaScript source of the TRACE scorer
def trace_script() -> str:
    return TRACE_SCRIPT.read_text(encoding="utf-8")


# Loads (or replaces) the Trace UDF library so Cypher can call Trace.scoreCandidates
async def load_trace_udf(database: GraphDatabase) -> None:
    client = await database.connected_client()
    try:
        await database.within_time_limit(client.udf_load(TRACE_LIBRARY, trace_script(), True))
    except ResponseError as error:
        raise UdfRejectedError(f"FalkorDB did not accept the TRACE UDF: {error}") from error


# Runs a query that calls the Trace UDF, loading it again once if a restarted server forgot it
async def rows_with_trace_udf(
    database: GraphDatabase,
    graph_name: str,
    query: Query,
    params: dict[str, Any],
    timer: GraphTimer | None = None,
) -> list[dict[str, Any]]:
    try:
        return await database.rows(graph_name, query, params, timer)
    except ResponseError as error:
        if UNKNOWN_TRACE_FUNCTION not in str(error):
            raise
    await load_trace_udf(database)
    return await database.rows(graph_name, query, params, timer)
