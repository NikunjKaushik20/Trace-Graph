import time
from dataclasses import dataclass

from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.ops import ADD_SPEND, READ_SPEND


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Prices:
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float

    # Dollar cost of one call: cached input tokens are billed at the cheaper cached price
    def cost(self, usage: TokenUsage) -> float:
        fresh_input = max(0, usage.input_tokens - usage.cached_tokens)
        return (
            fresh_input * self.input_per_million
            + usage.cached_tokens * self.cached_input_per_million
            + usage.output_tokens * self.output_per_million
        ) / 1_000_000


@dataclass(frozen=True)
class SpendReport:
    usd: float
    limit_usd: float
    calls: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int

    # True once spending has reached the limit and the paid model must stop
    @property
    def limit_reached(self) -> bool:
        return self.usd >= self.limit_usd


class SpendMeter:
    # Keeps the running total in FalkorDB, so restarts and other processes see the same number
    def __init__(
        self, database: GraphDatabase, ops_graph: str, prices: Prices, limit_usd: float
    ) -> None:
        self.database = database
        self.ops_graph = ops_graph
        self.prices = prices
        self.limit_usd = limit_usd

    # Adds one paid call to the meter and returns the new total
    async def add(self, usage: TokenUsage) -> float:
        params = {
            "usd": self.prices.cost(usage),
            "input_tokens": usage.input_tokens,
            "cached_tokens": usage.cached_tokens,
            "output_tokens": usage.output_tokens,
            "t": time.time(),
        }
        rows = await self.database.rows(self.ops_graph, ADD_SPEND, params)
        return float(rows[0]["usd"])

    # Reads the meter; before the ops graph exists, nothing has been spent
    async def report(self) -> SpendReport:
        rows = await self.database.rows(self.ops_graph, READ_SPEND, {})
        row = rows[0] if rows else {}
        return SpendReport(
            usd=float(row.get("usd", 0.0)),
            limit_usd=self.limit_usd,
            calls=int(row.get("calls", 0)),
            input_tokens=int(row.get("input_tokens", 0)),
            cached_tokens=int(row.get("cached_tokens", 0)),
            output_tokens=int(row.get("output_tokens", 0)),
        )
