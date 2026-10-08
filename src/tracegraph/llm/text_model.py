from collections.abc import Callable
from typing import Protocol


class LlmUnavailableError(RuntimeError):
    pass


class TextModel(Protocol):
    # Sends one system and one user message and returns the reply text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str: ...


class ScriptedModel:
    # Wraps a Python function that plays the part of the model
    def __init__(self, reply: Callable[[str, str], str]) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    # Answers from a Python function instead of an LLM, for tests and replay
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        self.calls.append((system, prompt))
        return self.reply(system, prompt)
