import time
from dataclasses import asdict
from typing import Any

from mcp.client.client import Client

from tracegraph.agent.citations import check_citations
from tracegraph.agent.mcp_calls import call_mcp_tool, openai_tools
from tracegraph.agent.mcp_server import build_mcp_server
from tracegraph.agent.narration import left_in_escrow, receipt_narration, remembered_note
from tracegraph.agent.planner import plan_jobs
from tracegraph.agent.prompts import BUYER_SYSTEM, JOB_BRIEF, RETRY_CITATIONS, STEP_CAP_REACHED
from tracegraph.agent.runs import AgentEvent, EventSink, JobRun, TaskRun, ToolStep, ignore_event
from tracegraph.agent.session import AgentSession
from tracegraph.llm.chat import ChatModel, Message, ToolCall, assistant_message, tool_result_message
from tracegraph.llm.text_model import LlmUnavailableError
from tracegraph.market.tasks import PlannedJob, TaskPlan, open_task


class BuyerAgent:
    # One buyer agent: its session, the model that picks its tools, and who hears what it does
    def __init__(self, session: AgentSession, model: ChatModel, events: EventSink = ignore_event):
        self.session = session
        self.model = model
        self.events = events

    # Plans a task with the LLM, then works through the plan
    async def run_task(self, task_id: str, task_text: str) -> TaskRun:
        plan = await plan_jobs(self.model, task_id, task_text)
        return await self.run_plan(task_id, task_text, plan)

    # Records a planned task in the graph and works each job through the MCP tools
    async def run_plan(self, task_id: str, task_text: str, plan: list[PlannedJob]) -> TaskRun:
        await self.emit("plan", None, {"task_id": task_id, "jobs": [asdict(job) for job in plan]})
        task = TaskPlan(task_id, self.session.buyer_id, task_text, plan, time.time())
        await open_task(self.session.database, self.session.graph_name, task)
        run = TaskRun(task_id, self.session.buyer_id, task_text)
        async with Client(build_mcp_server(self.session)) as client:
            tools = openai_tools((await client.list_tools()).tools)
            memory_note = ""
            for job in plan:
                job_run = await self.run_job(client, tools, run, job, memory_note)
                run.jobs.append(job_run)
                memory_note = memory_note or remembered_note(job_run)
        return run

    # Lets the model work one job through the tools up to the step cap, then checks its summary
    async def run_job(
        self,
        client: Client,
        tools: list[dict[str, Any]],
        run: TaskRun,
        job: PlannedJob,
        memory_note: str,
    ) -> JobRun:
        job_run = JobRun(job.job_id, job.capability)
        messages = self.opening_messages(run, job, memory_note)
        try:
            await self.work_through_tools(client, tools, messages, job_run)
        except LlmUnavailableError as error:
            await self.emit("error", job.job_id, {"message": str(error)})
        if left_in_escrow(job_run):
            job_run.steps.append(await self.call_tool(client, job.job_id, settle_call(job.job_id)))
            job_run.settled_by_safety_net = True
        await self.finish_narration(messages, job_run)
        await self.emit(
            "narration", job.job_id, {"text": job_run.narration, **asdict(job_run.citations)}
        )
        return job_run

    # The tool loop: ask the model, run the tools it picks, until it answers or the cap is hit
    async def work_through_tools(
        self, client: Client, tools: list[dict[str, Any]], messages: list[Message], job_run: JobRun
    ) -> None:
        for _ in range(self.session.settings.agent_max_steps):
            reply = await self.model.chat(messages, tools)
            messages.append(assistant_message(reply))
            if not reply.tool_calls:
                job_run.narration = reply.content or ""
                return
            for call in reply.tool_calls:
                step = await self.call_tool(client, job_run.job_id, call)
                job_run.steps.append(step)
                messages.append(tool_result_message(call, step.text_for_model()))
        job_run.hit_step_cap = True
        messages.append({"role": "user", "content": STEP_CAP_REACHED})
        closing = await self.model.chat(messages, None)
        job_run.narration = closing.content or ""

    # Calls one tool over MCP and reports it as it happens
    async def call_tool(self, client: Client, job_id: str, call: ToolCall) -> ToolStep:
        await self.emit("tool_call", job_id, {"name": call.name, "arguments": call.arguments})
        step = await call_mcp_tool(client, call)
        await self.emit(
            "tool_result", job_id, {"name": call.name, "ok": step.ok, "result": step.result}
        )
        return step

    # Keeps the model's summary only if every id it cites is real; one retry, then the receipt
    async def finish_narration(self, messages: list[Message], job_run: JobRun) -> None:
        graph = self.session.graph_name
        database = self.session.database
        check = await check_citations(database, graph, job_run.narration)
        if job_run.narration and not check.passed:
            messages.append(
                {
                    "role": "user",
                    "content": RETRY_CITATIONS.format(unknown=", ".join(check.unknown)),
                }
            )
            try:
                reply = await self.model.chat(messages, None)
                job_run.narration = reply.content or ""
            except LlmUnavailableError:
                job_run.narration = ""
            check = await check_citations(database, graph, job_run.narration)
            check.retried = True
        if not job_run.narration or not check.passed:
            job_run.narration = receipt_narration(job_run)
            check.fell_back_to_receipt = True
        job_run.citations = check

    # The system prompt and the brief for one job
    def opening_messages(self, run: TaskRun, job: PlannedJob, memory_note: str) -> list[Message]:
        brief = JOB_BRIEF.format(
            task_id=run.task_id,
            task_text=run.task_text,
            job_id=job.job_id,
            capability=job.capability,
            input_text=job.input_text,
            memory_note=memory_note,
        )
        return [
            {"role": "system", "content": BUYER_SYSTEM.format(buyer_id=self.session.buyer_id)},
            {"role": "user", "content": brief},
        ]

    # Sends an event to whoever is watching this agent
    async def emit(self, kind: str, job_id: str | None, data: dict[str, Any]) -> None:
        await self.events(AgentEvent(kind, self.session.buyer_id, job_id, data))


# The settle call the safety net makes when a job was left with money in escrow
def settle_call(job_id: str) -> ToolCall:
    return ToolCall("safety-net-settle", "settle", {"job_id": job_id})
