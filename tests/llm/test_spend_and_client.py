from types import SimpleNamespace
from typing import Any

import pytest

from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.client import (
    Endpoint,
    OpenAiCompatibleModel,
    parse_arguments,
    reply_from_response,
)
from tracegraph.llm.spend import Prices, SpendMeter, SpendReport, TokenUsage

GPT_4O_MINI = Prices(0.15, 0.075, 0.60)


def test_cost_bills_cached_input_at_the_cached_price() -> None:
    usage = TokenUsage(input_tokens=1_000_000, cached_tokens=400_000, output_tokens=100_000)
    assert GPT_4O_MINI.cost(usage) == pytest.approx(0.6 * 0.15 + 0.4 * 0.075 + 0.1 * 0.60)


def test_a_typical_decision_costs_about_a_tenth_of_a_cent() -> None:
    usage = TokenUsage(input_tokens=8_000, cached_tokens=0, output_tokens=500)
    assert GPT_4O_MINI.cost(usage) == pytest.approx(0.0015)


def test_the_limit_is_reached_at_the_limit() -> None:
    assert SpendReport(1.80, 1.80, 0, 0, 0, 0).limit_reached
    assert not SpendReport(1.79, 1.80, 0, 0, 0, 0).limit_reached


class FixedMeter(SpendMeter):
    # Starts at a fixed spend instead of reading FalkorDB
    def __init__(self, usd: float) -> None:
        super().__init__(GraphDatabase("redis://unused:1"), "ops", GPT_4O_MINI, 1.80)
        self.usd = usd

    # Reports the fixed spend
    async def report(self) -> SpendReport:
        return SpendReport(self.usd, self.limit_usd, 0, 0, 0, 0)


@pytest.mark.parametrize(("spent", "expected"), [(0.50, "paid"), (1.80, "free"), (2.10, "free")])
async def test_the_paid_endpoint_is_used_only_under_the_limit(spent: float, expected: str) -> None:
    free = Endpoint("free", "https://free", "key", "gpt-4o-mini", False)
    paid = Endpoint("paid", "https://paid", "key", "gpt-4o-mini", True)
    model = OpenAiCompatibleModel(free, paid, FixedMeter(spent))
    assert (await model.choose_endpoint()).name == expected


def test_tool_calls_and_cached_tokens_are_read_from_a_response() -> None:
    call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(name="trace_score", arguments='{"job_id": "job-1"}'),
    )
    usage = SimpleNamespace(
        prompt_tokens=900,
        completion_tokens=40,
        prompt_tokens_details=SimpleNamespace(cached_tokens=512),
    )
    response: Any = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))],
        usage=usage,
    )
    reply = reply_from_response(response, "free")
    assert reply.tool_calls[0].name == "trace_score"
    assert reply.tool_calls[0].arguments == {"job_id": "job-1"}
    assert reply.usage == TokenUsage(900, 512, 40)


def test_garbled_arguments_are_passed_on_for_the_tool_to_refuse() -> None:
    assert parse_arguments('{"job_id": ') == {"unreadable_arguments": '{"job_id": '}
    assert parse_arguments(None) == {}
