from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    falkordb_url: str = "redis://localhost:6379"
    shared_graph: str = "market"
    ops_graph: str = "ops"
    scoreboard_graph: str = "scoreboard"
    results_dir: str = "results"

    llm_base_url: str = "https://models.github.ai/inference"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"

    paid_llm_base_url: str = "https://api.openai.com/v1"
    paid_llm_api_key: str = ""
    paid_llm_model: str = "gpt-4o-mini"
    use_paid_llm: bool = False

    llm_mode: Literal["live", "record", "replay"] = "live"
    replay_path: str = "replays/demo.json"
    llm_seed: int = 7

    spend_limit_usd: float = 1.80
    price_input_per_million: float = 0.15
    price_cached_input_per_million: float = 0.075
    price_output_per_million: float = 0.60

    scorer: Literal["udf", "python"] = "udf"
    guard_mode: Literal["closed", "open", "unguarded"] = "closed"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    agent_max_steps: int = 8
    mcp_buyer_id: str = "buyer-1"
    investigator_questions_per_visitor: int = 10
    investigator_max_steps: int = 4

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]
    web_dir: str = "web/dist"
    admin_token: str = ""
    mcp_over_http: bool = False
    mcp_allowed_hosts: list[str] = ["localhost:*", "127.0.0.1:*"]


# Reads settings once from the environment and .env
@lru_cache
def get_settings() -> Settings:
    return Settings()
