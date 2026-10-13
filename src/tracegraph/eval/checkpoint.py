import json
from dataclasses import asdict
from pathlib import Path

from tracegraph.eval.outcomes import SeedResult

CHECKPOINT_FILE = "scoreboard-progress.jsonl"

MarketKey = tuple[str, str, int]


# Where finished markets are written while a scoreboard runs
def checkpoint_path(results_dir: str) -> Path:
    return Path(results_dir) / CHECKPOINT_FILE


# The lane, adversary and seed that identify one market
def market_key(result: SeedResult) -> MarketKey:
    return (result.lane, result.adversary, result.seed)


# Markets already played under the same frozen settings, so a restarted run can skip them
def load_finished(path: Path, settings_hash: str) -> dict[MarketKey, SeedResult]:
    finished: dict[MarketKey, SeedResult] = {}
    if not path.exists():
        return finished
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["settings_hash"] == settings_hash:
            result = SeedResult(**entry["result"])
            finished[market_key(result)] = result
    return finished


# Appends one finished market to the checkpoint file
def append_finished(path: Path, settings_hash: str, result: SeedResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as checkpoint:
        entry = {"settings_hash": settings_hash, "result": asdict(result)}
        checkpoint.write(json.dumps(entry) + "\n")
