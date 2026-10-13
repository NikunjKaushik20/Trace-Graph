from dataclasses import dataclass
from typing import Literal

from tracegraph.evidence.rules import GuardRules

Attack = Literal["none", "praise", "badmouth"]
Guard = Literal["closed", "open", "unguarded"]


@dataclass(frozen=True)
class Lane:
    name: str
    shared: bool
    attack: Attack
    guard: Guard
    funding_visible: float
    quarantine: bool
    shows: str

    # The write-guard rules this lane reads with
    @property
    def rules(self) -> GuardRules:
        if self.guard == "unguarded":
            return GuardRules.unguarded()
        if self.guard == "open":
            return GuardRules.open_with_funding_check()
        return GuardRules.closed_fleet()


LANES = (
    Lane("alone", False, "none", "closed", 1.0, False, "each buyer keeps its own graph"),
    Lane("together", True, "none", "closed", 1.0, False, "one shared graph, no attack"),
    Lane("poisoned", True, "praise", "unguarded", 1.0, False, "20 Sybils praise a ring, no guard"),
    Lane("guarded", True, "praise", "open", 1.0, False, "same attack, funding check on"),
    Lane("guarded_half_hidden", True, "praise", "open", 0.5, False, "half the Sybils hide funding"),
    Lane("quarantine", True, "praise", "open", 0.5, True, "half hidden, ring found and blocked"),
    Lane("bad_mouthed", True, "badmouth", "open", 1.0, False, "Sybils report fake failures"),
)

LANES_BY_NAME = {lane.name: lane for lane in LANES}
