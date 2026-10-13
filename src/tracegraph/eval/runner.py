import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

from tracegraph.eval.checkpoint import MarketKey
from tracegraph.eval.contract import Adversary, MarketContract, settings_hash, settings_json
from tracegraph.eval.lanes import LANES_BY_NAME
from tracegraph.eval.market_run import MarketRun
from tracegraph.eval.outcomes import SeedResult
from tracegraph.eval.saved_results import SCOREBOARD_FILE, keep_copy
from tracegraph.eval.summary import LaneSummary, demo_seed, summarise
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.scoreboard import SAVE_SCOREBOARD


@dataclass(frozen=True)
class ScoreboardPlan:
    falkordb_url: str
    lanes: list[str]
    adversaries: list[Adversary]
    seeds: list[int]
    workers: int


@dataclass(frozen=True)
class ScoreboardReport:
    run_id: str
    settings_hash: str
    demo_seed: int | None
    summaries: list[LaneSummary]


# Plays one lane on one seed in its own process, with its own connection
def play_one(url: str, lane_name: str, adversary: Adversary, seed: int) -> SeedResult:
    return asyncio.run(play_one_async(url, lane_name, adversary, seed))


# The async body of play_one
async def play_one_async(url: str, lane_name: str, adversary: Adversary, seed: int) -> SeedResult:
    database = GraphDatabase(url)
    try:
        run = MarketRun(database, MarketContract(), LANES_BY_NAME[lane_name], adversary, seed)
        return await run.play()
    finally:
        await database.close()


# Runs every market not already finished across worker processes and groups the results by lane
def run_all(
    plan: ScoreboardPlan,
    progress: Callable[[SeedResult], None],
    *,
    finished: dict[MarketKey, SeedResult],
) -> list[LaneSummary]:
    grouped: dict[tuple[str, str], list[SeedResult]] = defaultdict(list)
    for result in finished.values():
        grouped[(result.lane, result.adversary)].append(result)
    tasks = [
        (plan.falkordb_url, lane, adversary, seed)
        for lane in plan.lanes
        for adversary in plan.adversaries
        for seed in plan.seeds
        if (lane, adversary, seed) not in finished
    ]
    with ProcessPoolExecutor(max_workers=plan.workers) as pool:
        futures = [pool.submit(play_one, *task) for task in tasks]
        try:
            for future in as_completed(futures):
                result = future.result()
                grouped[(result.lane, result.adversary)].append(result)
                progress(result)
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
    return [
        summarise(sorted(grouped[(lane, adversary)], key=lambda result: result.seed))
        for lane in plan.lanes
        for adversary in plan.adversaries
    ]


# Saves a finished scoreboard to a file first, then in FalkorDB, where the API reads it from
async def save_scoreboard(
    database: GraphDatabase,
    graph_name: str,
    plan: ScoreboardPlan,
    summaries: list[LaneSummary],
    *,
    results_dir: str,
) -> ScoreboardReport:
    contract = MarketContract()
    report = ScoreboardReport(
        run_id=f"scoreboard-{int(time.time())}",
        settings_hash=settings_hash(contract),
        demo_seed=demo_seed(summaries),
        summaries=summaries,
    )
    params = {
        "run_id": report.run_id,
        "settings_hash": report.settings_hash,
        "settings": settings_json(contract),
        "seeds": len(plan.seeds),
        "demo_seed": report.demo_seed,
        "t": time.time(),
        "lanes": [summary.as_row() for summary in summaries],
    }
    keep_copy(results_dir, SCOREBOARD_FILE, params)
    await database.run(graph_name, SAVE_SCOREBOARD, params)
    return report
