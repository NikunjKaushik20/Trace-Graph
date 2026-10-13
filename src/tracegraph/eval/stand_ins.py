import json
import re
from typing import Any

from tracegraph.llm.chat import ChatModel, ChatReply, Message
from tracegraph.llm.text_model import LlmUnavailableError

WORD = re.compile(r"[a-z]{5,}")


class CannedWorker:
    # Honest work without an LLM: a summary built from the input's own sentences
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return json.dumps({"summary": prompt[:400].strip()})

    # Providers never chat
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        raise LlmUnavailableError("the stand-in worker only completes")


class OverlapJudge:
    # A judge without an LLM: passes output that shares at least five long words with the input
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        fenced = re.findall(r"<<<\n(.*?)\n>>>", prompt, flags=re.DOTALL)
        if len(fenced) < 2:
            return "FAIL: could not read the input and the output"
        shared = set(WORD.findall(fenced[0].lower())) & set(WORD.findall(fenced[1].lower()))
        if len(shared) >= 5:
            return "PASS: the output is about the input"
        return "FAIL: the output ignores the input"

    # The judge never chats
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        raise LlmUnavailableError("the stand-in judge only completes")


class StandInModels:
    # Providers and the judge run without an LLM in the agent evals; only the buyer uses one
    def model_for(self, channel: str) -> ChatModel:
        if channel == "judge":
            return OverlapJudge()
        return CannedWorker()
