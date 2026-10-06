import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from falkordb.asyncio import FalkorDB
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from tracegraph.graph.queries.query import Query


class GraphUnavailableError(RuntimeError):
    pass


CONNECTION_ERRORS = (RedisConnectionError, RedisTimeoutError, OSError, TimeoutError)
MISSING_GRAPH = "empty key"


@dataclass
class QueryOutcome:
    rows: list[dict[str, Any]]
    run_time_ms: float


@dataclass
class GraphTimer:
    total_ms: float = 0.0
    by_query: dict[str, float] = field(default_factory=dict)

    # Adds one query's FalkorDB run time to the running total
    def add(self, query_name: str, run_time_ms: float) -> None:
        self.total_ms += run_time_ms
        self.by_query[query_name] = self.by_query.get(query_name, 0.0) + run_time_ms


class GraphDatabase:
    # Remembers the server address; the client opens on first use
    def __init__(self, url: str, query_timeout_seconds: float = 15.0) -> None:
        self.url = url
        self.query_timeout_seconds = query_timeout_seconds
        self.unplugged = False
        self._client: Any = None

    # The open client; checks the port first so a stopped server is reported in seconds
    async def connected_client(self) -> Any:
        if self.unplugged:
            raise GraphUnavailableError("FalkorDB was unplugged for the demo")
        if self._client is None:
            if not await port_is_open(self.url, 5.0):
                raise GraphUnavailableError(
                    f"FalkorDB is not reachable at {safe_address(self.url)}"
                )
            self._client = FalkorDB.from_url(self.url, socket_connect_timeout=3)
        return self._client

    # Returns True when FalkorDB accepts a connection and answers a ping
    async def is_reachable(self, timeout_seconds: float = 3.0) -> bool:
        try:
            client = await self.connected_client()
            await asyncio.wait_for(client.connection.ping(), timeout_seconds)
        except (GraphUnavailableError, *CONNECTION_ERRORS):
            self._client = None
            return False
        return True

    # Runs one named query on one graph and returns its rows; a graph not created yet has none
    async def run(
        self,
        graph_name: str,
        query: Query,
        params: dict[str, Any] | None = None,
        timer: GraphTimer | None = None,
    ) -> QueryOutcome:
        graph = (await self.connected_client()).select_graph(graph_name)
        send = graph.ro_query if query.read_only else graph.query
        try:
            result = await self.within_time_limit(send(query.text, params or {}))
        except ResponseError as error:
            if query.read_only and MISSING_GRAPH in str(error):
                return QueryOutcome(rows=[], run_time_ms=0.0)
            raise
        outcome = QueryOutcome(rows=rows_from_result(result), run_time_ms=result.run_time_ms)
        if timer is not None:
            timer.add(query.name, outcome.run_time_ms)
        return outcome

    # Runs a query and returns only its rows
    async def rows(
        self,
        graph_name: str,
        query: Query,
        params: dict[str, Any] | None = None,
        timer: GraphTimer | None = None,
    ) -> list[dict[str, Any]]:
        outcome = await self.run(graph_name, query, params, timer)
        return outcome.rows

    # Waits for a database call, turning a lost or slow server into GraphUnavailableError
    async def within_time_limit(self, call: Awaitable[Any]) -> Any:
        try:
            return await asyncio.wait_for(call, self.query_timeout_seconds)
        except CONNECTION_ERRORS as error:
            self._client = None
            raise GraphUnavailableError(f"FalkorDB stopped answering: {error}") from error

    # Returns the execution profile FalkorDB reports for a query
    async def profile(self, graph_name: str, query: Query, params: dict[str, Any]) -> list[str]:
        graph = (await self.connected_client()).select_graph(graph_name)
        plan = await self.within_time_limit(graph.profile(query.text, params))
        return [str(line) for line in plan.plan]

    # Lists every named graph on the server
    async def list_graphs(self) -> list[str]:
        client = await self.connected_client()
        names = await self.within_time_limit(client.list_graphs())
        return [name.decode() if isinstance(name, bytes) else str(name) for name in names]

    # Deletes a named graph if it exists
    async def delete_graph(self, graph_name: str) -> None:
        if graph_name in await self.list_graphs():
            graph = (await self.connected_client()).select_graph(graph_name)
            await self.within_time_limit(graph.delete())

    # Gives direct access to one graph for schema commands
    async def select(self, graph_name: str) -> Any:
        return (await self.connected_client()).select_graph(graph_name)

    # Closes the connection pool
    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Turns a FalkorDB result into a list of dicts keyed by column name
def rows_from_result(result: Any) -> list[dict[str, Any]]:
    columns = [column_name(column) for column in result.header]
    return [dict(zip(columns, row, strict=True)) for row in result.result_set]


# Reads a column name from a FalkorDB result header entry
def column_name(column: Any) -> str:
    name = column[1] if isinstance(column, list | tuple) else column
    return name.decode() if isinstance(name, bytes) else str(name)


# Host and port of a database URL, without the password, for messages people can see
def safe_address(url: str) -> str:
    address = urlparse(url)
    return f"{address.hostname or 'localhost'}:{address.port or 6379}"


# Checks the server port answers at all, so a stopped database is reported quickly
async def port_is_open(url: str, timeout_seconds: float) -> bool:
    address = urlparse(url)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(address.hostname or "localhost", address.port or 6379),
            timeout_seconds,
        )
    except (TimeoutError, OSError):
        return False
    writer.close()
    return True
