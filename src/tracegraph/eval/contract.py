import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from tracegraph.eval.lanes import LANES
from tracegraph.trace.settings import TraceSettings

Adversary = Literal["strat", "calib"]
ADVERSARIES: tuple[Adversary, ...] = ("strat", "calib")
FROZEN_SETTINGS_HASH = "64c070403707a300f6c2a042d6ed2ab70c08c4cd0f9b93aa341a366c5b81d1a2"


@dataclass(frozen=True)
class MarketContract:
    providers: int = 1000
    malicious_share: float = 0.30
    buyers: int = 5
    rounds: int = 60
    delay_rounds: int = 2
    min_price_sats: int = 5
    max_price_sats: int = 20
    honest_failure_rate: float = 0.10
    high_price_sats: int = 13
    high_price_default_rate: float = 0.50
    calib_honest_jobs: int = 2
    ring_providers: int = 30
    sybil_writers: int = 20
    fake_writes_per_round: int = 5
    first_seed: int = 1000
    seed_count: int = 100

    # The seeds every lane runs on, the same list for every lane
    @property
    def seeds(self) -> list[int]:
        return list(range(self.first_seed, self.first_seed + self.seed_count))


# Everything that decides a scoreboard number, as sorted JSON
def settings_json(contract: MarketContract) -> str:
    frozen = {
        "contract": asdict(contract),
        "trace": asdict(TraceSettings()),
        "lanes": [asdict(lane) for lane in LANES],
        "adversaries": list(ADVERSARIES),
    }
    return json.dumps(frozen, sort_keys=True)


# SHA-256 of the settings, stored with every run so a changed contract shows up
def settings_hash(contract: MarketContract) -> str:
    return hashlib.sha256(settings_json(contract).encode()).hexdigest()
