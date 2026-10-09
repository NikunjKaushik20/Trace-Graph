import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

Capability = Literal["summarise", "extract_keywords", "translate"]
CAPABILITIES: tuple[Capability, ...] = ("summarise", "extract_keywords", "translate")


class SummaryOutput(BaseModel):
    summary: str = Field(min_length=20, max_length=600)


class KeywordsOutput(BaseModel):
    keywords: list[str] = Field(min_length=3, max_length=8)


class TranslationOutput(BaseModel):
    language: Literal["fr"]
    text: str = Field(min_length=1, max_length=2000)


OUTPUT_MODELS: dict[Capability, type[BaseModel]] = {
    "summarise": SummaryOutput,
    "extract_keywords": KeywordsOutput,
    "translate": TranslationOutput,
}

INSTRUCTIONS: dict[Capability, str] = {
    "summarise": 'Summarise the text in at most 60 words. Reply as JSON: {"summary": "..."}',
    "extract_keywords": (
        'List 3 to 8 keywords that best describe the text. Reply as JSON: {"keywords": [...]}'
    ),
    "translate": 'Translate the text into French. Reply as JSON: {"language": "fr", "text": "..."}',
}


@dataclass(frozen=True)
class WorkOrder:
    job_id: str
    capability: Capability
    input_text: str
    price_sats: int


@dataclass(frozen=True)
class Delivery:
    job_id: str
    provider_id: str
    output: dict[str, Any] | None
    note: str = ""

    # True when the provider sent any output
    @property
    def delivered(self) -> bool:
        return self.output is not None


# Checks a delivery against the output schema for its capability; returns the problem or None
def schema_problem(capability: Capability, output: dict[str, Any]) -> str | None:
    try:
        OUTPUT_MODELS[capability].model_validate(output)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "output"
        return f"{field}: {first['msg']}"
    return None


# Pulls the first JSON object out of a model reply, tolerating code fences around it
def parse_json_object(reply: str) -> dict[str, Any] | None:
    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(reply[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
