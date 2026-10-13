import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tracegraph.config import Settings
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.agent_eval import SAVE_AGENT_EVAL
from tracegraph.graph.queries.query import Query
from tracegraph.graph.queries.scoreboard import SAVE_SCOREBOARD

SCOREBOARD_FILE = "scoreboard.json"
AGENT_EVAL_FILE = "agent-eval.json"


@dataclass(frozen=True)
class SavedResult:
    file_name: str
    query: Query
    graph_name: str


# Writes the exact parameters a save query was given, so the run can be stored again later
def keep_copy(folder: str, file_name: str, params: dict[str, Any]) -> Path:
    path = Path(folder) / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(params, indent=1, sort_keys=True), encoding="utf-8")
    return path


# The saved runs this deployment knows about, and the graph each one belongs in
def saved_results(settings: Settings) -> list[SavedResult]:
    return [
        SavedResult(SCOREBOARD_FILE, SAVE_SCOREBOARD, settings.scoreboard_graph),
        SavedResult(AGENT_EVAL_FILE, SAVE_AGENT_EVAL, settings.ops_graph),
    ]


# Stores every kept run back in FalkorDB; runs already there are left alone by the save queries
async def restore_saved_results(database: GraphDatabase, settings: Settings) -> list[str]:
    restored = []
    for saved in saved_results(settings):
        path = Path(settings.results_dir) / saved.file_name
        if path.exists():
            params = json.loads(path.read_text(encoding="utf-8"))
            await database.run(saved.graph_name, saved.query, params)
            restored.append(str(params["run_id"]))
    return restored
