import hashlib
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from tracegraph.agent.investigator import Investigator
from tracegraph.api.schemas import QuestionRequest
from tracegraph.api.state import AppState, get_state
from tracegraph.graph.queries.ops import COUNT_QUESTION
from tracegraph.llm.text_model import LlmUnavailableError

router = APIRouter(tags=["investigator"])
State = Annotated[AppState, Depends(get_state)]


# L3: a visitor asks about the market and the investigator answers through read-only tools
@router.post("/investigator/ask")
async def ask(
    question: QuestionRequest,
    request: Request,
    state: State,
    visitor_id: Annotated[str | None, Header(max_length=64)] = None,
) -> dict[str, Any]:
    visitor = visitor_id or anonymous_visitor(request)
    asked = await count_question(state, visitor)
    allowed = state.settings.investigator_questions_per_visitor
    if asked > allowed:
        raise HTTPException(429, f"each visitor can ask {allowed} questions")
    model = state.models.model_for("investigator")
    investigator = Investigator(state.observer(), model, state.settings.investigator_max_steps)
    try:
        answer = await investigator.ask(question.question)
    except LlmUnavailableError as error:
        raise HTTPException(503, f"the language model is not available: {error}") from error
    return {**answer.as_dict(), "questions_left": max(allowed - asked, 0)}


# Adds one to the visitor's question count in the ops graph and returns the new total
async def count_question(state: AppState, visitor: str) -> int:
    params = {"visitor_id": visitor, "t": time.time()}
    rows = await state.database.rows(state.settings.ops_graph, COUNT_QUESTION, params)
    return int(rows[0]["questions"])


# A stable id for a visitor that sent none, from their address, without storing the address
def anonymous_visitor(request: Request) -> str:
    address = request.client.host if request.client else "unknown"
    return "anon-" + hashlib.sha256(address.encode()).hexdigest()[:16]
