import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from tracegraph.market.providers import Behaviour

CaseKind = Literal["clean", "new_provider", "close_call", "outside_praise", "ring"]
CaseLabel = Literal["clean", "suspicious", "ring"]

NAMES = ["amber", "birch", "cedar", "delta", "ember", "fjord", "grove", "harbor", "iris", "juno"]
CASE_MIX: list[tuple[CaseKind, int]] = [
    ("clean", 40),
    ("new_provider", 10),
    ("close_call", 10),
    ("outside_praise", 10),
    ("ring", 30),
]
CASE_TEXTS = [
    "Graph databases store data as nodes and the relationships between them. Queries follow "
    "those relationships directly instead of joining tables, which keeps multi-hop questions fast.",
    "A payment channel lets two parties send many small payments while touching the blockchain "
    "only twice: once to open the channel and once to settle the final balance.",
    "Sybil attacks create many fake identities to gain influence in a network. Reputation "
    "systems that count every identity equally are easy to sway this way.",
    "Escrow holds a buyer's money until the work is checked. If the work passes, the seller is "
    "paid; if it fails, the buyer gets the money back.",
    "Personalised PageRank measures how close each node is to a chosen set of trusted nodes by "
    "simulating random walks that keep returning to those nodes.",
]


@dataclass(frozen=True)
class CaseProvider:
    provider_id: str
    price_sats: int
    behaviour: Behaviour
    history: str
    outside_praise: int = 0
    in_ring: bool = False


@dataclass(frozen=True)
class AgentCase:
    case_id: str
    kind: CaseKind
    text: str
    providers: list[CaseProvider]

    # clean, suspicious (flags but no ring) or ring: what the agent should conclude
    @property
    def label(self) -> CaseLabel:
        if self.kind == "clean":
            return "clean"
        return "ring" if self.kind == "ring" else "suspicious"

    # Providers that take the money and do not do the work
    @property
    def malicious(self) -> set[str]:
        return {p.provider_id for p in self.providers if p.behaviour != "honest"}

    # Listed price of one provider in this case
    def price_of(self, provider_id: str) -> int:
        return next(p.price_sats for p in self.providers if p.provider_id == provider_id)


# An honest provider with a track record from other buyers
def established(name: str, rng: random.Random, successes: int, failures: int = 0) -> CaseProvider:
    history = "o" * successes + "x" * failures
    return CaseProvider(f"prov-{name}", rng.randint(9, 16), "honest", history)


# Three honest providers with clearly different records: TRACE should be confident
def clean_case(names: list[str], rng: random.Random) -> list[CaseProvider]:
    return [
        established(names[0], rng, rng.randint(9, 11)),
        established(names[1], rng, rng.randint(5, 6), 1),
        established(names[2], rng, rng.randint(3, 4), 1),
    ]


# Two known providers and a cheap newcomer with one or two good jobs: flagged, but honest
def new_provider_case(names: list[str], rng: random.Random) -> list[CaseProvider]:
    newcomer = CaseProvider(
        f"prov-{names[2]}", rng.randint(6, 9), "honest", "o" * rng.randint(1, 2)
    )
    return [*clean_case(names, rng)[:2], newcomer]


# Two providers with the same record at the top: a close call, but both honest
def close_call_case(names: list[str], rng: random.Random) -> list[CaseProvider]:
    successes = rng.randint(7, 9)
    return [
        established(names[0], rng, successes),
        established(names[1], rng, successes),
        established(names[2], rng, rng.randint(3, 4), 1),
    ]


# A newcomer praised by outside writers who have no money ties to it: uncounted, but honest
def outside_praise_case(names: list[str], rng: random.Random) -> list[CaseProvider]:
    praised = CaseProvider(
        f"prov-{names[2]}", rng.randint(7, 10), "honest", "oo", rng.randint(5, 8)
    )
    return [*clean_case(names, rng)[:2], praised]


# Two or three cheap scammers, funded from one hub, praised by writers funded from the same hub
def ring_case(names: list[str], rng: random.Random) -> list[CaseProvider]:
    ring = [
        CaseProvider(f"prov-{name}", rng.randint(5, 7), "scam", "", rng.randint(8, 12), True)
        for name in names[2 : 2 + rng.randint(2, 3)]
    ]
    return clean_case(names, rng)[:2] + ring


BUILDERS: dict[CaseKind, Callable[[list[str], random.Random], list[CaseProvider]]] = {
    "clean": clean_case,
    "new_provider": new_provider_case,
    "close_call": close_call_case,
    "outside_praise": outside_praise_case,
    "ring": ring_case,
}


# The 100 labelled hiring cases, the same every time for the same seed
def build_cases(seed: int = 7, limit: int | None = None) -> list[AgentCase]:
    rng = random.Random(seed)
    cases: list[AgentCase] = []
    for kind, count in CASE_MIX:
        for _ in range(count):
            names = rng.sample(NAMES, 5)
            providers = BUILDERS[kind](names, rng)
            rng.shuffle(providers)
            case_id = f"case-{len(cases) + 1:03d}"
            cases.append(AgentCase(case_id, kind, rng.choice(CASE_TEXTS), providers))
    rng.shuffle(cases)
    return cases[:limit] if limit else cases
