import time

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.policies import QUARANTINE_RING, RECORD_FUNDING_TRACE, RECORD_RING
from tracegraph.investigation.funding import FundingPath, funding_path
from tracegraph.investigation.quarantine import QuarantinePolicy
from tracegraph.investigation.rings import RingReport, find_ring


class QuarantineRefusedError(RuntimeError):
    pass


class InvestigationCase:
    # Investigation of one decision; every step is written onto that decision
    def __init__(
        self,
        database: GraphDatabase,
        graph_name: str,
        decision_id: str,
        timer: GraphTimer | None = None,
    ) -> None:
        self.database = database
        self.graph_name = graph_name
        self.decision_id = decision_id
        self.timer = timer

    # Follows the money between a writer and a provider and notes the result on the decision
    async def trace_funding(self, writer_id: str, provider_id: str) -> FundingPath:
        path = await funding_path(
            self.database, self.graph_name, writer_id, provider_id, self.timer
        )
        params = {
            "decision_id": self.decision_id,
            "provider_id": provider_id,
            "writer_id": writer_id,
            "node_ids": path.node_ids,
            "hops": path.hops,
            "t": time.time(),
        }
        await self.database.run(self.graph_name, RECORD_FUNDING_TRACE, params, self.timer)
        return path

    # Looks for a ring around a provider and, if there is one, stores it against the decision
    async def look_for_ring(self, provider_id: str) -> RingReport:
        report = await find_ring(self.database, self.graph_name, provider_id, self.timer)
        if report.is_ring:
            params = {
                "decision_id": self.decision_id,
                "ring_id": report.ring_id,
                "hub_id": report.hub_id,
                "bridge_id": report.bridge_id,
                "member_ids": report.member_ids,
                "t": time.time(),
            }
            await self.database.run(self.graph_name, RECORD_RING, params, self.timer)
        return report

    # Quarantines a ring; the graph refuses unless this decision found it and traced money into it
    async def quarantine(self, ring_id: str, reason: str) -> QuarantinePolicy:
        params = {
            "decision_id": self.decision_id,
            "ring_id": ring_id,
            "policy_id": f"policy-{ring_id}-{self.decision_id}",
            "reason": reason,
            "t": time.time(),
        }
        rows = await self.database.rows(self.graph_name, QUARANTINE_RING, params, self.timer)
        if not rows:
            raise QuarantineRefusedError(
                "quarantine needs find_ring on this ring and a funding path into it, "
                "both on the same decision"
            )
        row = rows[0]
        covered = sorted(str(provider) for provider in row["covered"])
        return QuarantinePolicy(
            str(row["policy_id"]), reason, str(row["created_by"]), self.decision_id, covered
        )
