from dataclasses import dataclass

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.investigation import FUNDING_PATH


@dataclass(frozen=True)
class FundingPath:
    writer_id: str
    provider_id: str
    node_ids: list[str]
    node_labels: list[list[str]]

    # True when some chain of FUNDED_BY links joins the writer and the provider
    @property
    def found(self) -> bool:
        return bool(self.node_ids)

    # Number of FUNDED_BY links on the path
    @property
    def hops(self) -> int:
        return max(0, len(self.node_ids) - 1)

    # Wallets and roots on the path: the money the writer and provider have in common
    @property
    def shared_funders(self) -> list[str]:
        return [
            node_id
            for node_id, labels in zip(self.node_ids, self.node_labels, strict=True)
            if "Wallet" in labels
        ]


# Finds the shortest FUNDED_BY chain between a writer and a provider
async def funding_path(
    database: GraphDatabase,
    graph_name: str,
    writer_id: str,
    provider_id: str,
    timer: GraphTimer | None = None,
) -> FundingPath:
    params = {"writer_id": writer_id, "provider_id": provider_id, "max_hops": 6}
    rows = await database.rows(graph_name, FUNDING_PATH, params, timer)
    if not rows:
        return FundingPath(writer_id, provider_id, [], [])
    row = rows[0]
    labels = [list(node_labels) for node_labels in row["node_labels"]]
    return FundingPath(writer_id, provider_id, list(row["node_ids"]), labels)
