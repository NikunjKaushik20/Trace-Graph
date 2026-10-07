from tracegraph.graph.queries.query import Query

ADD_SPEND = Query(
    name="add_spend",
    purpose="Adds one paid LLM call's tokens and cost to the spend meter in the ops graph.",
    read_only=False,
    text="""
MERGE (meter:SpendMeter {id: 'llm'})
ON CREATE SET meter.usd = 0.0, meter.calls = 0, meter.input_tokens = 0,
              meter.cached_tokens = 0, meter.output_tokens = 0
SET meter.usd = meter.usd + $usd,
    meter.calls = meter.calls + 1,
    meter.input_tokens = meter.input_tokens + $input_tokens,
    meter.cached_tokens = meter.cached_tokens + $cached_tokens,
    meter.output_tokens = meter.output_tokens + $output_tokens,
    meter.updated_at = $t
RETURN meter.usd AS usd
""",
)

READ_SPEND = Query(
    name="read_spend",
    purpose="Reads the spend meter: dollars spent on the paid LLM and tokens used.",
    text="""
OPTIONAL MATCH (meter:SpendMeter {id: 'llm'})
RETURN coalesce(meter.usd, 0.0) AS usd,
       coalesce(meter.calls, 0) AS calls,
       coalesce(meter.input_tokens, 0) AS input_tokens,
       coalesce(meter.cached_tokens, 0) AS cached_tokens,
       coalesce(meter.output_tokens, 0) AS output_tokens
""",
)

COUNT_QUESTION = Query(
    name="count_question",
    purpose="Counts one investigator question for a visitor and returns their running total.",
    read_only=False,
    text="""
MERGE (visitor:Visitor {id: $visitor_id})
SET visitor.questions = coalesce(visitor.questions, 0) + 1,
    visitor.last_seen = $t
RETURN visitor.questions AS questions
""",
)
