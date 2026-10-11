from dataclasses import dataclass

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.policies import ACTIVE_POLICIES


@dataclass(frozen=True)
class QuarantinePolicy:
    policy_id: str
    reason: str
    created_by: str
    decision_id: str | None
    covered: list[str]


# Every quarantine in force, oldest first
async def active_policies(
    database: GraphDatabase, graph_name: str, timer: GraphTimer | None = None
) -> list[QuarantinePolicy]:
    rows = await database.rows(graph_name, ACTIVE_POLICIES, {}, timer)
    return [
        QuarantinePolicy(
            policy_id=str(row["policy_id"]),
            reason=str(row["reason"]),
            created_by=str(row["created_by"]),
            decision_id=row["decision_id"],
            covered=sorted(str(provider) for provider in row["covered"]),
        )
        for row in rows
    ]
