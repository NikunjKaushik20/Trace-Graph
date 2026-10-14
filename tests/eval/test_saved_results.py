import json
import uuid
from pathlib import Path

import pytest

from tracegraph.config import Settings
from tracegraph.eval.outcomes import SeedResult
from tracegraph.eval.runner import ScoreboardPlan, save_scoreboard
from tracegraph.eval.saved_results import SCOREBOARD_FILE, keep_copy, restore_saved_results
from tracegraph.eval.summary import summarise
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.scoreboard import LATEST_SCOREBOARD


def test_a_kept_copy_is_the_exact_parameters_as_json(tmp_path: Path) -> None:
    path = keep_copy(str(tmp_path / "new-folder"), "run.json", {"run_id": "r1", "seeds": 3})
    assert json.loads(path.read_text(encoding="utf-8")) == {"run_id": "r1", "seeds": 3}


@pytest.mark.falkordb
async def test_a_kept_scoreboard_comes_back_once_after_the_graph_is_lost(
    database: GraphDatabase, tmp_path: Path
) -> None:
    settings = Settings(scoreboard_graph=f"test-scoreboard:{uuid.uuid4().hex[:8]}")
    settings = settings.model_copy(update={"results_dir": str(tmp_path)})
    results = [SeedResult("guarded", "strat", seed, fraud_sats=seed) for seed in (1, 2)]
    plan = ScoreboardPlan(settings.falkordb_url, ["guarded"], ["strat"], [1, 2], workers=1)
    try:
        report = await save_scoreboard(
            database,
            settings.scoreboard_graph,
            plan,
            [summarise(results)],
            results_dir=settings.results_dir,
        )
        assert (tmp_path / SCOREBOARD_FILE).exists()
        await database.delete_graph(settings.scoreboard_graph)
        assert await restore_saved_results(database, settings) == [report.run_id]
        await restore_saved_results(database, settings)
        latest = await database.rows(settings.scoreboard_graph, LATEST_SCOREBOARD)
        assert latest[0]["run_id"] == report.run_id
        graph = await database.select(settings.scoreboard_graph)
        runs = await graph.ro_query("MATCH (run:ScoreboardRun) RETURN count(run)")
        assert runs.result_set == [[1]]
    finally:
        await database.delete_graph(settings.scoreboard_graph)
