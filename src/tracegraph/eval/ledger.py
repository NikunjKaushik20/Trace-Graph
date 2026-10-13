import copy
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from tracegraph.evidence.reader import ReportRow, add_report, report_from_row
from tracegraph.trace.utility import ProviderEvidence

Edge = tuple[str, str]


@dataclass
class BuyerView:
    evidence: dict[str, ProviderEvidence]
    edge_counts: Counter[Edge]
    seed_writers: list[str]


@dataclass
class EvidenceLedger:
    seed_writers: list[str]
    delay_rounds: int
    shared: dict[str, ProviderEvidence] = field(default_factory=dict)
    edge_counts: Counter[Edge] = field(default_factory=Counter)
    pending: list[ReportRow] = field(default_factory=list)
    ignored_writers: dict[str, list[str]] = field(default_factory=dict)
    buyer_tally: Counter[str] = field(default_factory=Counter)

    # Adds one round of guarded reports; activity counts at once, outcomes wait for the delay
    def add_round(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            report = report_from_row(row)
            provider = self.provider(report.provider_id)
            provider.reports_received += 1
            provider.paid_jobs += 1 if report.job_id else 0
            provider.reviewer_funders[report.writer_id] = frozenset(row["writer_funders"] or [])
            self.pending.append(report)

    # Makes every report from round (now - delay) or earlier visible to all buyers
    def advance_to(self, round_index: int) -> None:
        visible_until = round_index - self.delay_rounds
        due = sorted(
            (report for report in self.pending if report.t <= visible_until),
            key=lambda report: report.sort_key,
        )
        self.pending = [report for report in self.pending if report.t > visible_until]
        for report in due:
            self.fold(report)

    # Applies one visible report to the shared evidence
    def fold(self, report: ReportRow) -> None:
        add_report(self.shared, report)
        if not report.counted:
            self.ignored_writers.setdefault(report.provider_id, []).append(report.writer_id)
            return
        if report.ok:
            self.edge_counts[(report.writer_id, report.provider_id)] += 1
        if report.writer_id in self.seed_writers:
            self.buyer_tally[report.provider_id] += 1 if report.ok else -5

    # What one buyer sees: everything visible to all, plus its own reports that are not yet
    def view_for(self, buyer_id: str) -> BuyerView:
        evidence = dict(self.shared)
        edge_counts = self.edge_counts
        own = [report for report in self.pending if report.writer_id == buyer_id]
        if own:
            edge_counts = Counter(self.edge_counts)
        for report in sorted(own, key=lambda report: report.sort_key):
            evidence[report.provider_id] = copy.deepcopy(evidence[report.provider_id])
            add_report(evidence, report)
            if report.counted and report.ok:
                edge_counts[(report.writer_id, report.provider_id)] += 1
        return BuyerView(evidence, edge_counts, self.seed_writers)

    # Marks quarantined providers and the ones that share funding with them
    def apply_quarantine(self, quarantined: list[str], contaminated: list[str]) -> None:
        for provider_id in quarantined:
            self.provider(provider_id).quarantined = True
        for provider_id in contaminated:
            self.provider(provider_id).contaminated = True

    # The shared evidence record for a provider, created the first time it is mentioned
    def provider(self, provider_id: str) -> ProviderEvidence:
        if provider_id not in self.shared:
            self.shared[provider_id] = ProviderEvidence(provider_id=provider_id)
        return self.shared[provider_id]
