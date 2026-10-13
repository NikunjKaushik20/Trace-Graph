from typing import Any

from mcp.client.client import Client

from tracegraph.agent.runs import ToolStep
from tracegraph.llm.chat import ToolCall


# MCP tool listings in the shape the OpenAI chat API expects
def openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


# Calls one tool over MCP; a refusal comes back as a failed step with the tool's message
async def call_mcp_tool(client: Client, call: ToolCall) -> ToolStep:
    result = await client.call_tool(call.name, call.arguments)
    if result.is_error:
        message = " ".join(getattr(part, "text", "") for part in result.content)
        return ToolStep(call.name, call.arguments, False, message)
    return ToolStep(call.name, call.arguments, True, dict(result.structured_content or {}))
