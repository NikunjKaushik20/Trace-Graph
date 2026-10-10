from dataclasses import dataclass
from typing import Literal

GuardMode = Literal["closed", "open", "unguarded"]


@dataclass(frozen=True)
class GuardRules:
    count_external_writers: bool
    check_funding: bool

    # Only admitted buyers count, and not when they share a funder with the provider
    @classmethod
    def closed_fleet(cls) -> "GuardRules":
        return cls(count_external_writers=False, check_funding=True)

    # Anyone counts unless they share a funder with the provider they rate
    @classmethod
    def open_with_funding_check(cls) -> "GuardRules":
        return cls(count_external_writers=True, check_funding=True)

    # Every write counts: the unguarded shared memory the paper's fix would open up
    @classmethod
    def unguarded(cls) -> "GuardRules":
        return cls(count_external_writers=True, check_funding=False)

    # Picks the rules for the guard mode named in the settings
    @classmethod
    def for_mode(cls, mode: str) -> "GuardRules":
        if mode == "open":
            return cls.open_with_funding_check()
        if mode == "unguarded":
            return cls.unguarded()
        return cls.closed_fleet()

    # Plain parameters for the guarded reports query
    def as_query_params(self) -> dict[str, bool]:
        return {
            "count_external_writers": self.count_external_writers,
            "check_funding": self.check_funding,
        }
