from dataclasses import dataclass, field
from typing import Any

from tracegraph.evidence.rules import GuardRules
from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.evidence import CANDIDATE_EVIDENCE
from tracegraph.trace.utility import ProviderEvidence


@dataclass(frozen=True)
class EvidenceRequest:
    graph_name: str
    buyer_id: str
    capability: str | None
    others_visible_until: float
    rules: GuardRules
    alone: bool = False
    as_of: float | None = None

    # Query parameters shared by the Python and the in-database scorer
    def as_query_params(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "me": self.buyer_id,
            "others_visible_until": self.others_visible_until,
            "seed_writers": [self.buyer_id] if self.alone else None,
            "as_of": self.as_of,
            **self.rules.as_query_params(),
        }


@dataclass
class ReportRow:
    provider_id: str
    writer_id: str
    admitted: bool
    ok: bool
    t: float
    job_id: str | None
    shared_funders: list[str]
    ignored_because: str | None

    # True when the write guard let this report count
    @property
    def counted(self) -> bool:
        return self.ignored_because is None

    # Time, then writer, then job: the order both scorers read reports in
    @property
    def sort_key(self) -> tuple[float, str, str]:
        return (self.t, self.writer_id, self.job_id or "")


@dataclass
class CandidateEvidence:
    evidence_by_provider: dict[str, ProviderEvidence]
    success_edges: list[tuple[str, str]]
    seed_writers: list[str]
    reports: list[ReportRow]
    prices: dict[str, int] = field(default_factory=dict)


# Reads everything TRACE needs about the candidates for one buyer's job, in one query
async def read_candidate_evidence(
    database: GraphDatabase, request: EvidenceRequest, timer: GraphTimer | None = None
) -> CandidateEvidence:
    rows = await database.rows(
        request.graph_name, CANDIDATE_EVIDENCE, request.as_query_params(), timer
    )
    row = rows[0] if rows else {}
    reports = [report_from_row(report) for report in row.get("reports") or []]
    return assemble_evidence(
        reports,
        list(row.get("providers") or []),
        list(row.get("reviewer_funders") or []),
        [str(writer) for writer in row.get("seed_writers") or []],
    )


# Turns one guarded report into a typed record
def report_from_row(row: dict[str, Any]) -> ReportRow:
    return ReportRow(
        provider_id=str(row["provider_id"]),
        writer_id=str(row["writer_id"]),
        admitted=bool(row["admitted"]),
        ok=bool(row["ok"]),
        t=float(row["t"]),
        job_id=row["job_id"],
        shared_funders=list(row["shared_funders"] or []),
        ignored_because=row["ignored_because"],
    )


# Groups reports, provider activity and reviewer funders into one record per provider
def assemble_evidence(
    reports: list[ReportRow],
    provider_rows: list[dict[str, Any]],
    funder_rows: list[dict[str, Any]],
    seed_writers: list[str],
) -> CandidateEvidence:
    sorted_reports = sorted(reports, key=lambda report: report.sort_key)
    evidence_by_provider = {
        str(row["provider_id"]): evidence_from_activity(row) for row in provider_rows
    }
    for report in sorted_reports:
        add_report(evidence_by_provider, report)
    for row in funder_rows:
        provider = evidence_by_provider.get(str(row["provider_id"]))
        if provider is not None:
            provider.reviewer_funders[str(row["writer_id"])] = frozenset(row["funders"] or [])
    success_edges = [
        (report.writer_id, report.provider_id)
        for report in sorted_reports
        if report.counted and report.ok
    ]
    return CandidateEvidence(
        evidence_by_provider,
        success_edges,
        seed_writers,
        sorted_reports,
        prices_from(provider_rows),
    )


# Starts a provider's evidence from its activity row
def evidence_from_activity(row: dict[str, Any]) -> ProviderEvidence:
    return ProviderEvidence(
        provider_id=str(row["provider_id"]),
        reports_received=int(row["reports_received"]),
        paid_jobs=int(row["paid_jobs"]),
        quarantined=bool(row["quarantined"]),
        contaminated=bool(row["contaminated"]),
    )


# Adds one report to its provider: counted ones feed TRACE, ignored ones are tallied
def add_report(evidence_by_provider: dict[str, ProviderEvidence], report: ReportRow) -> None:
    provider = evidence_by_provider.get(report.provider_id)
    if provider is None:
        return
    if not report.counted:
        provider.ignored_claims += 1
        return
    provider.outcomes.append(report.ok)
    if report.ok:
        counts = provider.success_counts_by_writer
        counts[report.writer_id] = counts.get(report.writer_id, 0) + 1


# Price in sats for each candidate provider
def prices_from(provider_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["provider_id"]): int(row["price_sats"] or 0) for row in provider_rows}
