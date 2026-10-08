from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderListing:
    id: str
    name: str
    capability: str
    price_sats: int | None


@dataclass(frozen=True)
class BuyerAccount:
    id: str
    name: str
    admitted: bool
    balance_sats: int
    principal_id: str | None = None
    principal_name: str | None = None


@dataclass(frozen=True)
class FundingLink:
    funded_id: str
    funder_id: str


@dataclass(frozen=True)
class FundingChains:
    root_ids: list[str]
    wallet_ids: list[str]
    links: list[FundingLink]


@dataclass(frozen=True)
class SettledJob:
    job_id: str
    payment_id: str
    payer_id: str
    provider_id: str
    price_sats: int
    ok: bool
    t: float


@dataclass(frozen=True)
class UnpaidReport:
    writer_id: str
    provider_id: str
    ok: bool
    t: float


# Turns a list of records into the plain dicts a Cypher UNWIND expects
def as_rows(records: list[Any]) -> list[dict[str, Any]]:
    return [asdict(record) for record in records]
