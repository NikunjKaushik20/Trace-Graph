import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from tracegraph.config import Settings
from tracegraph.eval.agent_cases import AgentCase
from tracegraph.eval.agent_scores import LaneScore, ToolChoiceScore, lane_score, tool_choice_score
from tracegraph.eval.case_runs import CaseRun, EvalLane
from tracegraph.eval.graph_lane import run_graph_case
from tracegraph.eval.saved_results import AGENT_EVAL_FILE, keep_copy
from tracegraph.eval.text_lane import run_text_case
from tracegraph.graph.connection import GraphDatabase
from tracegraph.graph.queries.agent_eval import SAVE_AGENT_EVAL
from tracegraph.llm.chat import ChatModel
from tracegraph.llm.embeddings import Embedder
from tracegraph.llm.factory import ModelSource
from tracegraph.llm.replay import complete_with


@dataclass(frozen=True)
class AgentEvalReport:
    run_id: str
    lanes: list[LaneScore]
    tool_choice: ToolChoiceScore
    runs: list[CaseRun]


# Runs every case in each lane, one at a time so the free endpoint's rate limit holds
async def run_agent_eval(
    database: GraphDatabase,
    settings: Settings,
    *,
    models: ModelSource,
    embedder: Embedder,
    cases: list[AgentCase],
    lanes: list[EvalLane],
    progress: Callable[[CaseRun], None],
) -> AgentEvalReport:
    runs: list[CaseRun] = []
    for case in cases:
        for lane in lanes:
            model = models.model_for(f"eval-{lane}:{case.case_id}")
            if lane == "graph":
                run = await run_graph_case(database, settings, model, embedder, case)
            else:
                run = await run_text_case(TextAdapter(model), case)
            runs.append(run)
            progress(run)
    return AgentEvalReport(
        run_id=f"agent-eval-{int(time.time())}",
        lanes=[lane_score(lane, [run for run in runs if run.lane == lane]) for lane in lanes],
        tool_choice=tool_choice_score([run for run in runs if run.lane == "graph"]),
        runs=runs,
    )


class TextAdapter:
    # Lets a chat model answer one-shot prompts, so they are recorded and replayed like chat turns
    def __init__(self, model: ChatModel) -> None:
        self.model = model

    # One system and one user message as a single chat turn
    async def complete(self, system: str, prompt: str, max_tokens: int = 300) -> str:
        return await complete_with(self.model, system, prompt, max_tokens)


# Saves the eval to a file first, then in the ops graph so the API can show it
async def save_agent_eval(
    database: GraphDatabase,
    graph_name: str,
    model_name: str,
    report: AgentEvalReport,
    *,
    results_dir: str,
) -> None:
    params = {
        "run_id": report.run_id,
        "model": model_name,
        "cases": len({run.case_id for run in report.runs}),
        "t": time.time(),
        "l2": asdict(report.tool_choice),
        "lanes": [asdict(lane) for lane in report.lanes],
        "case_runs": [asdict(run) for run in report.runs],
    }
    keep_copy(results_dir, AGENT_EVAL_FILE, params)
    await database.run(graph_name, SAVE_AGENT_EVAL, params)
