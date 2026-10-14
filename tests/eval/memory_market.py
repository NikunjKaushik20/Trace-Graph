from collections import defaultdict
from typing import Any

from tracegraph.graph.connection import GraphDatabase, GraphTimer, QueryOutcome
from tracegraph.graph.queries.query import Query


class SchemaStub:
    # Accepts any schema command and does nothing
    def __getattr__(self, name: str) -> Any:
        # The schema command itself, awaited by apply_schema
        async def ignore(*args: Any, **kwargs: Any) -> None:
            return None

        return ignore


class MarketGraph:
    # What the scoreboard writes to one graph, kept in plain Python
    def __init__(self) -> None:
        self.admitted: set[str] = set()
        self.funder: dict[str, str] = {}
        self.reports: list[dict[str, Any]] = []

    # Funders up to 3 hops up the FUNDED_BY chain, like FUNDED_BY*1..3
    def funders_of(self, node_id: str) -> list[str]:
        found: list[str] = []
        current = node_id
        for _ in range(3):
            if current not in self.funder:
                break
            current = self.funder[current]
            found.append(current)
        return found

    # The write guard, applied the way the report_guard Cypher fragment does
    def guarded(self, report: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        writer_funders = self.funders_of(report["payer_id"])
        provider_funders = self.funders_of(report["provider_id"])
        shared = [funder for funder in writer_funders if funder in provider_funders]
        admitted = report["payer_id"] in self.admitted
        ignored = None
        if not admitted and not params["count_external_writers"]:
            ignored = "writer_not_admitted"
        elif params["check_funding"] and shared:
            ignored = "shares_funding_with_provider"
        return {
            "provider_id": report["provider_id"],
            "writer_id": report["payer_id"],
            "admitted": admitted,
            "ok": report["ok"],
            "t": report["t"],
            "job_id": report["job_id"],
            "shared_funders": shared,
            "ignored_because": ignored,
            "writer_funders": writer_funders,
        }


class MemoryMarketDatabase(GraphDatabase):
    # Answers the scoreboard's queries from memory, for tests that run without FalkorDB
    def __init__(self) -> None:
        super().__init__("redis://memory:0")
        self.graphs: dict[str, MarketGraph] = defaultdict(MarketGraph)

    # Runs one of the queries the scoreboard uses
    async def run(
        self,
        graph_name: str,
        query: Query,
        params: dict[str, Any] | None = None,
        timer: GraphTimer | None = None,
    ) -> QueryOutcome:
        graph = self.graphs[graph_name]
        params = params or {}
        rows: list[dict[str, Any]] = []
        if query.name == "create_buyers":
            graph.admitted |= {row["id"] for row in params["buyers"] if row["admitted"]}
        elif query.name == "link_funding":
            graph.funder |= {link["funded_id"]: link["funder_id"] for link in params["links"]}
        elif query.name == "record_settled_jobs":
            graph.reports += params["jobs"]
        elif query.name == "round_reports":
            due = [report for report in graph.reports if report["t"] == params["t"]]
            rows = [graph.guarded(report, params) for report in due]
        return QueryOutcome(rows=rows, run_time_ms=0.0)

    # Hands apply_schema a stub that accepts every command
    async def select(self, graph_name: str) -> Any:
        return SchemaStub()

    # Lists the graphs written so far
    async def list_graphs(self) -> list[str]:
        return list(self.graphs)

    # Forgets a graph
    async def delete_graph(self, graph_name: str) -> None:
        self.graphs.pop(graph_name, None)
