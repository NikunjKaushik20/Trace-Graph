from dataclasses import dataclass
from typing import cast

from fastapi import Request

from tracegraph.agent.assembly import build_session
from tracegraph.agent.session import AgentSession
from tracegraph.api.task_runs import TaskRegistry
from tracegraph.config import Settings
from tracegraph.evidence.rules import GuardMode
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.names import View
from tracegraph.llm.embeddings import Embedder
from tracegraph.llm.factory import ModelSource


@dataclass
class AppState:
    settings: Settings
    database: GraphDatabase
    models: ModelSource
    embedder: Embedder
    tasks: TaskRegistry
    guard_mode: GuardMode
    live_lanes: int = 0

    # Settings as they stand now, with the guard mode the admin last chose
    def current_settings(self) -> Settings:
        return self.settings.model_copy(update={"guard_mode": self.guard_mode})

    # A buyer's session with the marketplace, ready to hire and pay
    def buyer_session(self, buyer_id: str, view: View = "together") -> AgentSession:
        return build_session(
            self.current_settings(),
            self.database,
            buyer_id,
            self.models,
            embedder=self.embedder,
            view=view,
        )

    # A session that only reads: for receipts, the graph view and the investigator
    def observer(self, view: View = "together", buyer_id: str = "observer") -> AgentSession:
        return AgentSession(self.database, self.current_settings(), buyer_id, view=view)


# The app's state, for route functions
def get_state(request: Request) -> AppState:
    return cast(AppState, request.app.state.tracegraph)
