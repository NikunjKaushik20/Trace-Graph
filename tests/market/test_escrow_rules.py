from typing import Any

import pytest

from tracegraph.graph.connection import GraphDatabase
from tracegraph.market.escrow import Escrow, HireRequest
from tracegraph.market.paywall import Invoice

HIRE = HireRequest("buyer-1", "job-1", "prov-a", "dec-1")


class CannedDatabase(GraphDatabase):
    # Keeps the row every query will return
    def __init__(self, row: dict[str, Any] | None) -> None:
        super().__init__("redis://unused:6379")
        self.row = row

    # Returns the one canned hire-check row instead of asking FalkorDB
    async def rows(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [self.row] if self.row is not None else []


# A hire-check row for a provider that may be hired, with some fields overridden
def check_row(**changes: Any) -> dict[str, Any]:
    row = {
        "job_status": "planned",
        "balance_sats": 100,
        "price_sats": 12,
        "position": 1,
        "policies": [],
    }
    return {**row, **changes}


# An invoice for the hire above at the given price
def invoice(amount_sats: int = 12) -> Invoice:
    return Invoice("inv-1", "prov-a", "job-1", amount_sats, "hash")


@pytest.mark.parametrize(
    ("row", "amount", "expected"),
    [
        (check_row(), 12, None),
        (check_row(position=None), 12, "not in the top 3"),
        (check_row(position=4), 12, "not in the top 3"),
        (check_row(policies=["policy-1"]), 12, "quarantined by policy-1"),
        (check_row(job_status="held"), 12, "already held"),
        (check_row(), 30, "invoice asks 30 sats"),
        (check_row(balance_sats=5), 12, "cannot afford"),
        (None, 12, "not found"),
    ],
)
async def test_hire_rules(row: dict[str, Any] | None, amount: int, expected: str | None) -> None:
    reason = await Escrow(CannedDatabase(row), "market").refusal_reason(HIRE, invoice(amount))
    if expected is None:
        assert reason is None
    else:
        assert reason is not None and expected in reason
