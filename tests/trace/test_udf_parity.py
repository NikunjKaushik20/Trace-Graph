import json
import random
import shutil
import subprocess
from dataclasses import asdict
from typing import Any

import pytest

from tracegraph.evidence.reader import assemble_evidence, report_from_row
from tracegraph.graph.udf_loader import TRACE_SCRIPT
from tracegraph.trace.ranking import score_candidates
from tracegraph.trace.settings import TraceSettings

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

SETTINGS = TraceSettings()

HARNESS = """
const fs = require("fs");
const registered = {};
globalThis.falkor = { register: (name, fn) => { registered[name] = fn; } };
eval(fs.readFileSync(process.argv[1], "utf8"));
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const scores = registered.scoreCandidates(
  input.providers, input.reports, input.reviewer_funders, input.seed_writers, input.settings
);
process.stdout.write(JSON.stringify(scores));
"""


# A random market's evidence in the exact shape the candidate_evidence query returns
def random_evidence(seed: int, buyers: int = 5) -> dict[str, Any]:
    rng = random.Random(seed)
    providers = [
        {
            "provider_id": f"p-{index:02d}",
            "capability": "summarise",
            "price_sats": rng.randint(5, 20),
            "reports_received": 0,
            "paid_jobs": rng.randint(0, 15),
            "quarantined": rng.random() < 0.1,
            "contaminated": rng.random() < 0.1,
        }
        for index in range(25)
    ]
    writers = [f"buyer-{index}" for index in range(buyers)] + [f"sybil-{i}" for i in range(4)]
    reports = []
    for number in range(rng.randint(0, 300)):
        provider = rng.choice(providers)
        writer = rng.choice(writers)
        provider["reports_received"] += 1
        reports.append(random_report(rng, provider["provider_id"], writer, number))
    pairs = sorted({(report["provider_id"], report["writer_id"]) for report in reports})
    roots = [f"root-{index}" for index in range(6)]
    funders = [
        {"provider_id": provider, "writer_id": writer, "funders": rng.sample(roots, 2)}
        for provider, writer in pairs
    ]
    return {
        "providers": providers,
        "reports": reports,
        "reviewer_funders": funders,
        "seed_writers": writers[:buyers],
    }


# One report from a writer; outsiders' reports are sometimes ignored by the guard
def random_report(
    rng: random.Random, provider_id: str, writer_id: str, number: int
) -> dict[str, Any]:
    outsider = writer_id.startswith("sybil")
    reasons = [None, "writer_not_admitted", "shares_funding_with_provider"]
    return {
        "provider_id": provider_id,
        "writer_id": writer_id,
        "admitted": not outsider,
        "ok": rng.random() < 0.8,
        "t": float(rng.randint(0, 40)),
        "job_id": f"job-{number}" if rng.random() < 0.9 else None,
        "shared_funders": [],
        "ignored_because": rng.choice(reasons) if outsider else None,
    }


# Scores the evidence with the JavaScript UDF source, run under Node
def scores_from_javascript(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = json.dumps({**evidence, "settings": asdict(SETTINGS)})
    completed = subprocess.run(
        [str(NODE), "-e", HARNESS, str(TRACE_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return {score["provider_id"]: score for score in json.loads(completed.stdout)}


# Scores the same evidence with the Python copy of TRACE
def scores_from_python(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = assemble_evidence(
        [report_from_row(report) for report in evidence["reports"]],
        evidence["providers"],
        evidence["reviewer_funders"],
        evidence["seed_writers"],
    )
    scores = score_candidates(
        candidates.evidence_by_provider,
        candidates.success_edges,
        candidates.seed_writers,
        SETTINGS,
    )
    return {score.provider_id: asdict(score) for score in scores}


@pytest.mark.parametrize("seed", range(12))
def test_javascript_and_python_scorers_agree(seed: int) -> None:
    evidence = random_evidence(seed, buyers=1 if seed % 4 == 0 else 5)
    from_javascript = scores_from_javascript(evidence)
    from_python = scores_from_python(evidence)
    assert from_javascript.keys() == from_python.keys()
    for provider_id, python_score in from_python.items():
        javascript_score = from_javascript[provider_id]
        for field_name, python_value in python_score.items():
            if isinstance(python_value, float):
                assert javascript_score[field_name] == pytest.approx(python_value, abs=1e-9)
            else:
                assert javascript_score[field_name] == python_value, (provider_id, field_name)
