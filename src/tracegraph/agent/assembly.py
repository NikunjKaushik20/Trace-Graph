import random
from collections.abc import Mapping

from tracegraph.agent.session import AgentSession
from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.names import View, graph_for_buyer
from tracegraph.llm.embeddings import Embedder
from tracegraph.llm.factory import ModelSource
from tracegraph.market.escrow import Escrow
from tracegraph.market.hiring import Marketplace
from tracegraph.market.paywall import MockLightning
from tracegraph.market.providers import Behaviour, ProviderAgent, work_for
from tracegraph.market.roster import DEMO_PROVIDERS
from tracegraph.trace.settings import TraceSettings


# The marketplace on one market graph: escrow, mock Lightning, the provider agents and the judge
def build_marketplace(
    database: GraphDatabase,
    graph_name: str,
    models: ModelSource,
    hireable_count: int,
    behaviours: Mapping[str, Behaviour] | None = None,
) -> Marketplace:
    lightning = MockLightning()
    behaviours = behaviours or {provider.id: provider.behaviour for provider in DEMO_PROVIDERS}
    providers = {
        provider_id: ProviderAgent(
            provider_id,
            work_for(behaviour, models.model_for(f"provider:{provider_id}"), random.Random(index)),
            lightning,
        )
        for index, (provider_id, behaviour) in enumerate(sorted(behaviours.items()))
    }
    escrow = Escrow(database, graph_name, hireable_count)
    return Marketplace(escrow, lightning, providers, models.model_for("judge"))


# A buyer's session wired to the database, the marketplace and the embedder
def build_session(
    settings: Settings,
    database: GraphDatabase,
    buyer_id: str,
    models: ModelSource,
    *,
    embedder: Embedder | None,
    view: View = "together",
) -> AgentSession:
    trace_settings = TraceSettings()
    graph_name = graph_for_buyer(settings.shared_graph, buyer_id, view)
    marketplace = build_marketplace(database, graph_name, models, trace_settings.hireable_count)
    return AgentSession(
        database=database,
        settings=settings,
        buyer_id=buyer_id,
        marketplace=marketplace,
        embedder=embedder,
        view=view,
        trace_settings=trace_settings,
    )
