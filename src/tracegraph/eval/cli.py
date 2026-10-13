import argparse
import asyncio
import os
import sys
import time
from typing import cast

from tracegraph.config import get_settings
from tracegraph.eval.checkpoint import MarketKey, append_finished, checkpoint_path, load_finished
from tracegraph.eval.contract import (
    ADVERSARIES,
    FROZEN_SETTINGS_HASH,
    Adversary,
    MarketContract,
    settings_hash,
)
from tracegraph.eval.lanes import LANES
from tracegraph.eval.outcomes import SeedResult
from tracegraph.eval.runner import ScoreboardPlan, run_all, save_scoreboard
from tracegraph.eval.summary import LaneSummary
from tracegraph.graph.connection import GraphDatabase


# Reads the command line: how many seeds, which lanes and adversaries, how many processes
def parse_plan(argv: list[str]) -> ScoreboardPlan:
    contract = MarketContract()
    parser = argparse.ArgumentParser(
        prog="tracegraph-scoreboard",
        description="Run the Section 7.3 market in FalkorDB for every lane and seed.",
    )
    parser.add_argument(
        "--seeds", type=int, default=contract.seed_count, help="how many seeds, from 1000"
    )
    parser.add_argument(
        "--lanes", default=",".join(lane.name for lane in LANES), help="comma-separated lanes"
    )
    parser.add_argument(
        "--adversaries", default=",".join(ADVERSARIES), help="comma-separated: strat, calib"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
        help="processes playing markets at once",
    )
    args = parser.parse_args(argv)
    return ScoreboardPlan(
        falkordb_url=get_settings().falkordb_url,
        lanes=args.lanes.split(","),
        adversaries=[cast(Adversary, name) for name in args.adversaries.split(",")],
        seeds=contract.seeds[: args.seeds],
        workers=args.workers,
    )


# One line per lane: the numbers the scoreboard shows
def summary_line(summary: LaneSummary) -> str:
    return (
        f"{summary.lane:<20} {summary.adversary:<6} mean {summary.mean:7.1f} "
        f"(se {summary.se:5.1f})  median {summary.median:6.1f}  p90 {summary.p90:7.1f}  "
        f"max {summary.max:6.0f}  malicious {summary.malicious_share:5.1%}  "
        f"{summary.mean_round_ms:5.1f} ms/round"
    )


# Runs the scoreboard with no LLM anywhere, prints it, keeps a copy and stores it in FalkorDB
def run_scoreboard() -> None:
    plan = parse_plan(sys.argv[1:])
    total = len(plan.lanes) * len(plan.adversaries) * len(plan.seeds)
    current = settings_hash(MarketContract())
    frozen = "frozen" if current == FROZEN_SETTINGS_HASH else "CHANGED since freezing"
    checkpoint = checkpoint_path(get_settings().results_dir)
    finished = planned_only(plan, load_finished(checkpoint, current))
    print(f"settings {current[:12]} ({frozen}), {total} markets, {len(finished)} already played")
    started = time.time()
    played = [len(finished)]

    # Writes each finished market to the checkpoint and prints a line every 20 markets
    def progress(result: SeedResult) -> None:
        append_finished(checkpoint, current, result)
        played[0] += 1
        if played[0] % 20 == 0 or played[0] == total:
            print(f"  {played[0]}/{total} markets, {time.time() - started:.0f}s", flush=True)

    summaries = run_all(plan, progress, finished=finished)
    for summary in summaries:
        print(summary_line(summary))
    report = asyncio.run(store(plan, summaries))
    checkpoint.unlink(missing_ok=True)
    print(f"saved {report}")


# Keeps only the checkpointed markets this plan asks for
def planned_only(
    plan: ScoreboardPlan, finished: dict[MarketKey, SeedResult]
) -> dict[MarketKey, SeedResult]:
    return {
        key: result
        for key, result in finished.items()
        if key[0] in plan.lanes and key[1] in plan.adversaries and key[2] in plan.seeds
    }


# Saves the results to the scoreboard graph
async def store(plan: ScoreboardPlan, summaries: list[LaneSummary]) -> str:
    settings = get_settings()
    database = GraphDatabase(settings.falkordb_url)
    try:
        report = await save_scoreboard(
            database,
            settings.scoreboard_graph,
            plan,
            summaries,
            results_dir=settings.results_dir,
        )
    finally:
        await database.close()
    return f"{report.run_id}, demo seed {report.demo_seed}"
