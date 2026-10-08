import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tracegraph.llm.chat import ChatModel, ChatReply, Message, ToolCall
from tracegraph.llm.spend import TokenUsage
from tracegraph.llm.text_model import LlmUnavailableError


class ReplayStore:
    # A JSON file of recorded LLM replies, one ordered list per channel (a buyer, the judge, ...)
    def __init__(self, path: Path) -> None:
        self.path = path
        self.channels: dict[str, list[dict[str, Any]]] = {}
        if path.exists():
            self.channels = json.loads(path.read_text(encoding="utf-8"))

    # Appends one reply to a channel and writes the file
    def append(self, channel: str, reply: ChatReply) -> None:
        self.channels.setdefault(channel, []).append(asdict(reply))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.channels, indent=1, ensure_ascii=False), "utf-8")

    # The reply recorded at a position in a channel, or None past the end
    def reply_at(self, channel: str, position: int) -> ChatReply | None:
        replies = self.channels.get(channel, [])
        if position >= len(replies):
            return None
        saved = replies[position]
        calls = [ToolCall(**call) for call in saved["tool_calls"]]
        return ChatReply(saved["content"], calls, TokenUsage(**saved["usage"]), "replay")


class RecordingModel:
    # Passes calls to a live model and records every reply on one channel
    def __init__(self, live: ChatModel, store: ReplayStore, channel: str) -> None:
        self.live = live
        self.store = store
        self.channel = channel

    # Calls the live model and records its reply
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        reply = await self.live.chat(messages, tools, max_tokens)
        self.store.append(self.channel, reply)
        return reply

    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return await complete_with(self, system, prompt, max_tokens)


class ReplayModel:
    # Plays a channel's recorded replies back in order, so a demo run is free and identical
    def __init__(self, store: ReplayStore, channel: str) -> None:
        self.store = store
        self.channel = channel
        self.position = 0

    # Returns the next recorded reply on this channel
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        reply = self.store.reply_at(self.channel, self.position)
        if reply is None:
            raise LlmUnavailableError(f"replay has no more recorded replies for {self.channel}")
        self.position += 1
        return reply

    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return await complete_with(self, system, prompt, max_tokens)


# A plain text completion built on a model's chat method
async def complete_with(model: ChatModel, system: str, prompt: str, max_tokens: int) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    reply = await model.chat(messages, None, max_tokens)
    return reply.content or ""
