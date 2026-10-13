import argparse
import asyncio
import sys
from typing import cast

from tracegraph.config import Settings, get_settings
from tracegraph.eval.agent_cases import build_cases
from tracegraph.eval.agent_eval import AgentEvalReport, run_agent_eval, save_agent_eval
from tracegraph.eval.case_runs import CaseRun, EvalLane
from tracegraph.graph.connection import GraphDatabase
from tracegraph.llm.embeddings import LocalEmbedder
from tracegraph.llm.factory import ModelFactory, spend_meter


# Reads the command line and runs the agent evals
def run_agent_evals() -> None:
    parser = argparse.ArgumentParser(
        prog="tracegraph-agent-eval",
        description="Run the buyer on labelled hiring cases with and without the graph.",
    )
    parser.add_argument("--cases", type=int, default=100, help="how many labelled cases")
    parser.add_argument("--lanes", default="graph,text", help="comma-separated: graph, text")
    args = parser.parse_args(sys.argv[1:])
    lanes = [cast(EvalLane, lane) for lane in args.lanes.split(",")]
    asyncio.run(evaluate(get_settings(), args.cases, lanes))


# Runs the cases, prints L1 and L2, saves them in FalkorDB and shows what the LLM cost
async def evaluate(settings: Settings, case_count: int, lanes: list[EvalLane]) -> None:
    database = GraphDatabase(settings.falkordb_url)
    try:
        embedder = LocalEmbedder(settings.embedding_model, settings.embedding_dimensions)
        cases = build_cases(limit=case_count)
        models = ModelFactory(settings, database)
        report = await run_agent_eval(
            database,
            settings,
            models=models,
            embedder=embedder,
            cases=cases,
            lanes=lanes,
            progress=print_case,
        )
        print_report(report)
        await save_agent_eval(
            database,
            settings.ops_graph,
            settings.paid_llm_model if settings.use_paid_llm else settings.llm_model,
            report,
            results_dir=settings.results_dir,
        )
        spend = await spend_meter(settings, database).report()
        print(f"paid LLM spend so far: ${spend.usd:.3f} of ${spend.limit_usd:.2f}")
    finally:
        await database.close()


# One line per finished case
def print_case(run: CaseRun) -> None:
    hired = run.hired or "nobody"
    flag = " SCAM" if run.hired_malicious else ""
    print(f"  {run.case_id} {run.label:<10} {run.lane:<5} hired {hired}{flag} {run.tool_path}")


# L1 per lane and the L2 tool-choice score
def print_report(report: AgentEvalReport) -> None:
    for lane in report.lanes:
        print(
            f"L1 {lane.lane:<5} scams hired {lane.scams_hired}/{lane.cases}, "
            f"{lane.sats_to_scams} sats to scams, no hire {lane.no_hire}, errors {lane.errors}"
        )
    choice = report.tool_choice
    print(
        f"L2 investigated {choice.rings_investigated}/{choice.ring_cases} rings, "
        f"{choice.other_cases_investigated} other cases; precision {choice.precision:.2f}, "
        f"recall {choice.recall:.2f}; quarantines {choice.quarantines} "
        f"({choice.quarantines_backed} backed, {choice.false_quarantines} false); "
        f"citations passed {choice.citation_pass_rate:.0%}"
    )
