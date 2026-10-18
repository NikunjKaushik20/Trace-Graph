# Build rules

Every phase is checked against this list before it is marked done. If a rule is broken on purpose, the reason goes in `DEVIATIONS.md`.

## Scope

- [ ] Build what `IDEA.md` says. Anything different is logged in `DEVIATIONS.md` with what IDEA.md said, what we did, why it is better, and how to undo it.
- [ ] A deviation is allowed only when it makes the project better. "Easier" is not a reason.
- [ ] The backend is in `src/`; the site is in `web/` and only reads the HTTP API (D40).
- [ ] Fresh code only. Nothing is copied from `D:\sats_router` or `D:\trace-api`. Ideas from the TRACE paper and SatsRouter are allowed and get cited.
- [ ] Synthetic or public data only.

## Code style

- [ ] Names say what a thing is or does: `count_reports_for`, `release_payment`, `ProviderScore`. No abbreviations except domain terms from the paper (`lcb`, `cusum`, `ppr`, `sats`) and common ones (`id`, `url`, `llm`).
- [ ] One `#` comment line directly above every function definition, saying what it does in plain words. Test functions are the one exception: their names are full sentences (`test_proven_provider_beats_a_newcomer`), so a comment would repeat the name. Test helpers still get a comment.
- [ ] One `#` comment line above a call only when it is a main step of a flow (for example each step of the agent loop or a simulation round).
- [ ] No other comments. No file header comments, no docstrings, no commented-out code, no TODOs.
- [ ] No file over about 250 lines. No function over about 40 lines. Split by meaning, not by size alone.
- [ ] Type hints on every function. Plain data goes in dataclasses or pydantic models, not loose dicts.
- [ ] No clever one-liners when two plain lines read better.

## Writing (comments, strings, docs, prompts)

Checked against the humanizer skill and Wikipedia's "Signs of AI writing" list.

- [ ] Plain words. None of: robust, seamless, leverage, utilize, ensure, delve, crucial, pivotal, comprehensive, cutting-edge, powerful, streamlined, "serves as", "stands as".
- [ ] No "not just X but Y", no "it's not X, it's Y", no stacked lists of three as decoration.
- [ ] No trailing "-ing" clauses that add fake analysis ("..., highlighting the need for ...").
- [ ] Sentence-case headings, no emoji, bold only where a reader truly needs it.
- [ ] At most one em dash per paragraph.
- [ ] Numbers in docs come from code we ran, never from memory.

## Graph

- [ ] FalkorDB is the only store for evidence, decisions, payments, policies and memory. No shadow copy in Python, files or another database.
- [ ] If FalkorDB is down, the agent refuses to pay (fails closed).
- [ ] Every Cypher query lives in `src/tracegraph/graph/queries/` as a named `Query` with a one-line purpose. `QUERIES.md` is generated from them.
- [ ] Queries take parameters. User input is never formatted into query text.
- [ ] The graph holds only what a buyer could observe. Ground truth (who is malicious) stays in the simulator.

## Agent and LLM

- [ ] The agent uses typed MCP tools only. It never writes free-form Cypher.
- [ ] The agent can only pay a provider from the ranked set the graph returned for that job.
- [ ] LLM endpoint, key and model come from environment variables. Switching providers needs no code change.
- [ ] Paid spend is metered from the `usage` field of every response. At $1.80 the client switches to the free endpoint or to replay.
- [ ] The scoreboard never calls an LLM.
- [ ] Every node ID the agent cites is checked against the graph before it is shown.

## Quality gate per phase

- [ ] `uv run ruff check .` is clean.
- [ ] `uv run mypy src` is clean.
- [ ] `uv run pytest` passes. Tests that need FalkorDB are marked and run when the database is up.
- [ ] `docs/PHASES.md` is updated with what was built and what was checked.

## Not done by Claude

- [ ] No git commits. Nikunj commits.
- [ ] No AI-disclosure text in the README. Nikunj writes that section.
