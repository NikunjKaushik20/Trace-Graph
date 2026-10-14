from typing import Any

from tracegraph.llm.chat import ChatReply, Message


class ScriptedChatModel:
    # Plays a fixed list of replies to chat calls, and answers complete calls with a function
    def __init__(self, replies: list[ChatReply], complete_reply: str = "") -> None:
        self.replies = list(replies)
        self.complete_reply = complete_reply
        self.seen: list[list[Message]] = []

    # Returns the next scripted reply, or a plain closing line once the script runs out
    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None, max_tokens: int = 600
    ) -> ChatReply:
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else ChatReply("Nothing more to do.")

    # Returns the fixed completion text
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return self.complete_reply
