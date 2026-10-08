import json
from dataclasses import dataclass
from typing import Any

import openai
from openai import AsyncOpenAI

from tracegraph.llm.chat import ChatReply, Message, ToolCall
from tracegraph.llm.spend import SpendMeter, TokenUsage
from tracegraph.llm.text_model import LlmUnavailableError

LLM_ERRORS = (openai.APIConnectionError, openai.APITimeoutError, openai.APIStatusError)


@dataclass(frozen=True)
class Endpoint:
    name: str
    base_url: str
    api_key: str
    model: str
    paid: bool


class OpenAiCompatibleModel:
    # Talks to OpenAI-compatible endpoints; the paid one only while the meter is under its limit
    def __init__(
        self, free: Endpoint, paid: Endpoint | None, meter: SpendMeter | None, seed: int = 7
    ) -> None:
        self.free = free
        self.paid = paid
        self.meter = meter
        self.seed = seed
        self._clients: dict[str, AsyncOpenAI] = {}

    # One chat turn, with tools when given; paid calls are added to the spend meter
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        endpoint = await self.choose_endpoint()
        request: dict[str, Any] = {
            "model": endpoint.model,
            "messages": messages,
            "temperature": 0,
            "seed": self.seed,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
        try:
            response = await self.client_for(endpoint).chat.completions.create(**request)
        except LLM_ERRORS as error:
            raise LlmUnavailableError(f"{endpoint.name} LLM call failed: {error}") from error
        reply = reply_from_response(response, endpoint.name)
        if endpoint.paid and self.meter is not None:
            await self.meter.add(reply.usage)
        return reply

    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        reply = await self.chat(messages, None, max_tokens)
        return reply.content or ""

    # The paid endpoint while there is budget left, otherwise the free one
    async def choose_endpoint(self) -> Endpoint:
        if self.paid is None or self.meter is None:
            return self.free
        report = await self.meter.report()
        return self.free if report.limit_reached else self.paid

    # One SDK client per endpoint, created on first use
    def client_for(self, endpoint: Endpoint) -> AsyncOpenAI:
        if not endpoint.api_key:
            raise LlmUnavailableError(f"no API key set for the {endpoint.name} LLM endpoint")
        if endpoint.name not in self._clients:
            self._clients[endpoint.name] = AsyncOpenAI(
                base_url=endpoint.base_url, api_key=endpoint.api_key, max_retries=2, timeout=60
            )
        return self._clients[endpoint.name]


# Reads text, tool calls and token usage out of an SDK response
def reply_from_response(response: Any, endpoint_name: str) -> ChatReply:
    message = response.choices[0].message
    calls = [
        ToolCall(call.id, call.function.name, parse_arguments(call.function.arguments))
        for call in message.tool_calls or []
        if call.type == "function"
    ]
    return ChatReply(message.content, calls, usage_from(response.usage), endpoint_name)


# Token counts from an SDK usage object, including cached input tokens when reported
def usage_from(usage: Any) -> TokenUsage:
    if usage is None:
        return TokenUsage()
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    return TokenUsage(usage.prompt_tokens or 0, cached, usage.completion_tokens or 0)


# Tool arguments as a dict; arguments the model garbled are passed on so the tool can refuse
def parse_arguments(raw: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"unreadable_arguments": raw}
    return parsed if isinstance(parsed, dict) else {"unreadable_arguments": raw}
