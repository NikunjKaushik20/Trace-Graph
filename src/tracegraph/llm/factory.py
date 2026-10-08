from pathlib import Path
from typing import Protocol

from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.chat import ChatModel
from tracegraph.llm.client import Endpoint, OpenAiCompatibleModel
from tracegraph.llm.replay import RecordingModel, ReplayModel, ReplayStore
from tracegraph.llm.spend import Prices, SpendMeter


# The spend meter for the paid endpoint, kept in the ops graph
def spend_meter(settings: Settings, database: GraphDatabase) -> SpendMeter:
    prices = Prices(
        settings.price_input_per_million,
        settings.price_cached_input_per_million,
        settings.price_output_per_million,
    )
    return SpendMeter(database, settings.ops_graph, prices, settings.spend_limit_usd)


# The live model: free endpoint always, paid endpoint too when it is switched on
def live_model(settings: Settings, database: GraphDatabase) -> OpenAiCompatibleModel:
    free = Endpoint("free", settings.llm_base_url, settings.llm_api_key, settings.llm_model, False)
    paid = None
    if settings.use_paid_llm:
        paid = Endpoint(
            "paid",
            settings.paid_llm_base_url,
            settings.paid_llm_api_key,
            settings.paid_llm_model,
            True,
        )
    return OpenAiCompatibleModel(free, paid, spend_meter(settings, database), settings.llm_seed)


class ModelSource(Protocol):
    # The model one channel should talk to
    def model_for(self, channel: str) -> ChatModel: ...


class ModelFactory:
    # Hands out one model per channel (a buyer, the judge, a provider) in the configured mode
    def __init__(self, settings: Settings, database: GraphDatabase) -> None:
        self.settings = settings
        self.live = live_model(settings, database)
        self.store = ReplayStore(Path(settings.replay_path))

    # The model one channel should talk to
    def model_for(self, channel: str) -> ChatModel:
        if self.settings.llm_mode == "replay":
            return ReplayModel(self.store, channel)
        if self.settings.llm_mode == "record":
            return RecordingModel(self.live, self.store, channel)
        return self.live
