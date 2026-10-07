from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    name: str
    purpose: str
    text: str
    read_only: bool = True
