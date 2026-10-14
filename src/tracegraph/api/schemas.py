from typing import Literal

from pydantic import BaseModel, Field

from tracegraph.evidence.rules import GuardMode

BUYER_ID = r"^buyer-[1-5]$"
SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$"


class TaskRequest(BaseModel):
    buyer_id: str = Field(pattern=BUYER_ID)
    text: str = Field(min_length=3, max_length=2000)
    view: Literal["together", "alone"] = "together"
    task_id: str | None = Field(default=None, pattern=SAFE_ID)


class TaskStarted(BaseModel):
    task_id: str
    buyer_id: str
    events_url: str


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class SeedRequest(BaseModel):
    with_ring: bool = False


class GuardRequest(BaseModel):
    mode: GuardMode


class PlugRequest(BaseModel):
    connected: bool
