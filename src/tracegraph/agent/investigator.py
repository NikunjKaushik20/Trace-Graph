import json
from dataclasses import dataclass, field
from typing import Any

from mcp.client.client import Client

from tracegraph.agent.citations import CitationCheck, check_citations, cited_ids
from tracegraph.agent.investigator_server import build_investigator_server
from tracegraph.agent.mcp_calls import call_mcp_tool, openai_tools
from tracegraph.agent.prompts import (
    INVESTIGATOR_FALLBACK,
    INVESTIGATOR_SYSTEM,
    RETRY_CITATIONS,
    STEP_CAP_REACHED,
)
from tracegraph.agent.runs import ToolStep
from tracegraph.agent.session import AgentSession
from tracegraph.llm.chat import ChatModel, Message, assistant_message, tool_result_message


@dataclass
class InvestigatorAnswer:
    question: str
    answer: str = ""
    steps: list[ToolStep] = field(default_factory=list)
    citations: CitationCheck = field(default_factory=CitationCheck)

    # Every node id the tools returned, for the UI to highlight as the path behind the answer
    @property
    def path_ids(self) -> list[str]:
        results = [step.result for step in self.steps if step.ok]
        return cited_ids(json.dumps(results, default=str))

    # The answer as plain JSON for the API
    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "tools": [
                {"name": step.name, "arguments": step.arguments, "ok": step.ok}
                for step in self.steps
            ],
            "path_ids": self.path_ids,
            "citations_passed": self.citations.passed,
            "fell_back_to_receipt": self.citations.fell_back_to_receipt,
        }


class Investigator:
    # Answers a visitor's question with read-only tools and a checked citation list
    def __init__(self, session: AgentSession, model: ChatModel, max_steps: int) -> None:
        self.session = session
        self.model = model
        self.max_steps = max_steps

    # Runs the tool loop for one question, then checks every id the answer cites
    async def ask(self, question: str) -> InvestigatorAnswer:
        result = InvestigatorAnswer(question)
        messages: list[Message] = [
            {"role": "system", "content": INVESTIGATOR_SYSTEM},
            {"role": "user", "content": question},
        ]
        async with Client(build_investigator_server(self.session)) as client:
            tools = openai_tools((await client.list_tools()).tools)
            result.answer = await self.look_up(client, tools, messages, result)
        await self.check_answer(messages, result)
        return result

    # Asks the model, runs the tools it picks, and returns its answer in words
    async def look_up(
        self,
        client: Client,
        tools: list[dict[str, Any]],
        messages: list[Message],
        result: InvestigatorAnswer,
    ) -> str:
        for _ in range(self.max_steps):
            reply = await self.model.chat(messages, tools)
            messages.append(assistant_message(reply))
            if not reply.tool_calls:
                return reply.content or ""
            for call in reply.tool_calls:
                step = await call_mcp_tool(client, call)
                result.steps.append(step)
                messages.append(tool_result_message(call, step.text_for_model()))
        messages.append({"role": "user", "content": STEP_CAP_REACHED})
        return (await self.model.chat(messages, None)).content or ""

    # Keeps the answer only if its ids are real nodes; one retry, then the list of records seen
    async def check_answer(self, messages: list[Message], result: InvestigatorAnswer) -> None:
        database, graph = self.session.database, self.session.graph_name
        check = await check_citations(database, graph, result.answer)
        if result.answer and not check.passed:
            retry = RETRY_CITATIONS.format(unknown=", ".join(check.unknown))
            messages.append({"role": "user", "content": retry})
            result.answer = (await self.model.chat(messages, None)).content or ""
            check = await check_citations(database, graph, result.answer)
            check.retried = True
        if not result.answer or not check.passed:
            result.answer = INVESTIGATOR_FALLBACK.format(ids=", ".join(result.path_ids) or "none")
            check.fell_back_to_receipt = True
        result.citations = check
