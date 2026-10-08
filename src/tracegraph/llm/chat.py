import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from tracegraph.llm.spend import TokenUsage

Message = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    endpoint: str = ""


class ChatModel(Protocol):
    # One chat turn with optional tools; the reply is text, tool calls, or both
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply: ...

    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str: ...


# The assistant message to append after a reply that asked for tools
def assistant_message(reply: ChatReply) -> Message:
    message: Message = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {"name": call.name, "arguments": json_text(call.arguments)},
            }
            for call in reply.tool_calls
        ]
    return message


# The message that hands one tool result back to the model
def tool_result_message(call: ToolCall, result_text: str) -> Message:
    return {"role": "tool", "tool_call_id": call.call_id, "content": result_text}


# Compact JSON for arguments sent back to the model
def json_text(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
