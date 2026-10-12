import random
from dataclasses import dataclass, field

from tracegraph.config import Settings
from tracegraph.evidence.rules import GuardRules
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.names import View, graph_for_buyer
from tracegraph.llm.embeddings import Embedder
from tracegraph.market.hiring import Marketplace
from tracegraph.trace.settings import TraceSettings


class ToolRefusedError(RuntimeError):
    pass


@dataclass
class AgentSession:
    database: GraphDatabase
    settings: Settings
    buyer_id: str
    marketplace: Marketplace | None = None
    embedder: Embedder | None = None
    view: View = "together"
    trace_settings: TraceSettings = field(default_factory=TraceSettings)
    tie_breaker: random.Random = field(default_factory=lambda: random.Random(7))
    decisions_per_job: dict[str, int] = field(default_factory=dict)

    # The graph this buyer reads and writes: the shared market, or its own in the Alone view
    @property
    def graph_name(self) -> str:
        return graph_for_buyer(self.settings.shared_graph, self.buyer_id, self.view)

    # Which writes count, from the guard mode in the settings
    @property
    def guard_rules(self) -> GuardRules:
        return GuardRules.for_mode(self.settings.guard_mode)

    # A readable id for the next decision on a job: dec-<job>-1, dec-<job>-2, ...
    def next_decision_id(self, job_id: str) -> str:
        count = self.decisions_per_job.get(job_id, 0) + 1
        self.decisions_per_job[job_id] = count
        return f"dec-{job_id}-{count}"

    # The marketplace, or a refusal when this session cannot pay anyone
    def require_marketplace(self) -> Marketplace:
        if self.marketplace is None:
            raise ToolRefusedError("this session has no marketplace, so it cannot hire or settle")
        return self.marketplace
