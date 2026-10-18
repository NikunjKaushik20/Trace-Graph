# Backend phases

Each phase ends with the quality gate in `BUILD_RULES.md`. Status is one of: pending, in progress, done, done (needs FalkorDB check).

| Phase | What it builds | Status |
|---|---|---|
| 0 | Project setup: settings, docker-compose with AOF, lint/type/test config, rules files | done |
| 1 | Graph layer: connection, named graphs, schema (constraints, range and vector indexes), the `Query` registry | done (needs FalkorDB check) |
| 2 | TRACE scoring in Python: LCB, default risk, CUSUM, exclusion, PPR, entropy, Sybil ratio, clique, utility, flags | done |
| 3 | Evidence and guard: recording outcomes, admission, funding provenance, ignored claims, Alone and Together views | done (needs FalkorDB check) |
| 4 | TRACE scoring inside FalkorDB: the JS UDF library and a parity test against phase 2 | done (needs FalkorDB check) |
| 5 | Market: providers, the 402 handshake, escrow, judge, settle, demo seed | done (needs FalkorDB check) |
| 6 | Investigation: funding path, ring finding (WCC, CDLP, PageRank, betweenness), quarantine policy | done (needs FalkorDB check) |
| 7 | Memory: lessons, embeddings, vector index, recall | done (needs FalkorDB check) |
| 8 | LLM client with spend meter, MCP server with the 11 tools, agent loop, citation check | done (needs FalkorDB check) |
| 9 | Scoreboard: the simulator, lanes, 100 seeds, results stored in FalkorDB | done (needs FalkorDB check) |
| 10 | Agent evals: with and without the graph (L1), tool-choice score (L2) | done (needs FalkorDB and a live LLM run) |
| 11 | HTTP API for the frontend: runs and live trace, receipts, investigator with per-visitor cap, profile, health | done (needs FalkorDB check) |
| 12 | README with setup and data model, generated QUERIES.md, ARCHITECTURE.md | done (results section waits for the final runs) |

## Log

(Each phase adds a short entry here: what was built, what was checked, anything left open.)

### Phase 0, setup
- `pyproject.toml` with ruff, mypy (strict) and pytest config; `docker-compose.yml` pinned to `falkordb/falkordb:v4.22.0` with AOF on; `.env.example`; `config.py`; `check.sh` runs the whole quality gate.
- Open: confirm the data volume path inside the container once Docker is installed.

### Phase 1, graph layer
- `graph/connection.py` (one async client, typed rows, FalkorDB run time per query, fast fail when the server is down), `graph/names.py`, `graph/schema.py` (unique ids, range indexes, the Lesson vector index), `graph/queries/query.py`.
- Open: run `apply_schema` against a live server.

### Phase 2, TRACE in Python
- `trace/reliability.py` (Bayesian LCB, failure-rate bound, smoothed risk, CUSUM, exclusion), `trace/graph_signals.py` (PPR, entropy, Sybil ratio, clique), `trace/utility.py`, `trace/ranking.py` (greedy order, seeded tie-break, flags, status).
- Checked: 22 unit tests.

### Phase 3, evidence and the write guard
- `graph/queries/evidence.py` (`candidate_evidence`), `graph/queries/market_setup.py`, `graph/queries/outcomes.py`, `evidence/rules.py` (closed fleet, open with funding check, unguarded), `evidence/reader.py`, `market/records.py`, `market/graph_writes.py`.
- Checked: unit tests for evidence assembly. Integration tests for the guard are written and skip until FalkorDB runs.
- Open: run `tests/evidence/test_guard_in_falkordb.py` live.

### Phase 4, TRACE inside FalkorDB
- `graph/udf/trace_score.js`, `graph/udf_loader.py`, `evidence/scoring.py` (the `udf` / `python` switch), `trace_scores` query.
- Checked: the parity test runs the JS file under Node on 12 random markets; every field matches Python to 1e-9. Changing one line of the JS fails 9 of 12 cases, so the test has teeth.
- Open: FalkorDB's UDF docs do not say a UDF can take lists and maps as arguments. If the live check fails, pass `toJSON(...)` strings instead and parse them in the JS.

### Phase 5, market
- `market/work.py` (capabilities and output schemas), `market/paywall.py` (402 reply, invoices, L402-style header, mock Lightning network), `market/providers.py` (honest, scam, strategic), `market/judge.py`, `market/escrow.py`, `market/hiring.py` (`Marketplace`), `market/tasks.py`, `market/roster.py` (the 12-provider demo market), `market/seed.py` and `market/cli.py` (`tracegraph-seed`), `graph/queries/jobs.py`, `graph/queries/decisions.py`, `evidence/decisions.py`, `llm/text_model.py`.
- Added `tools/check_style.py` to the gate: it fails on a missing comment line above a function, a docstring, a header comment, a file over 250 lines or a function over 40. It found 17 misses in phases 0 to 4, all fixed.
- Checked: unit tests for the handshake (forged and reused proofs are refused), the providers, the judge, the escrow rules and the roster's funding chains (every Sybil shares a funder with every ring provider within 3 hops; nobody else does).
- Open: `tests/market/test_paid_job_in_falkordb.py` (score, record decision, 402, hold, deliver, judge, release; and a refused hire) runs once FalkorDB is up.

### Phase 6, investigation
- `graph/queries/investigation.py` (`algo.SPpaths`, `algo.WCC`, `algo.labelPropagation`, `algo.pageRank`, `algo.betweenness`), `graph/queries/policies.py`, `investigation/funding.py`, `investigation/rings.py`, `investigation/quarantine.py`, `investigation/case.py` (`InvestigationCase`: each step is written onto the decision).
- Checked: unit tests for the ring helpers and funding-path properties.
- Open, FalkorDB checks: `tests/investigation/test_investigation_in_falkordb.py` expects the ring found from QuickDigest to be the 3 ring providers and 8 Sybils with `root-ring-hub` as hub, Summa not to be a ring, the quarantine to be refused twice (no trace, then a trace with no path) and accepted after a real trace, and TransFast to be excluded for buyer-3 afterwards. Two signatures to confirm live: `algo.pageRank(null, 'FUNDED_BY')` with a null label, and `algo.SPpaths` without `weightProp`.

### Phase 7, memory
- `llm/embeddings.py` (`LocalEmbedder` on fastembed `BAAI/bge-small-en-v1.5`; `HashingEmbedder` for tests), `graph/queries/memory.py`, `memory/lessons.py`, `memory/recall.py`.
- Checked: the local model loads and returns 384-dimension unit vectors, matching the vector index. Unit tests for lesson ranking and the test embedder.
- Open, FalkorDB checks: `tests/memory/test_memory_in_falkordb.py`. Confirm that `db.idx.vector.queryNodes` returns `score` as a distance (smaller is closer), since `similar_lessons` sorts by it ascending.

### Phase 8, LLM, MCP server and the buyer agent
- `llm/chat.py`, `llm/client.py` (one OpenAI-compatible client for GitHub Models and the paid key; paid only while the meter is under $1.80), `llm/spend.py` (the meter lives in the `ops` graph), `llm/replay.py` (record and replay per channel), `llm/factory.py`.
- `agent/session.py`, `agent/tools/` (one file per verb: lookups, deciding, investigating, acting, remembering, explaining), `agent/tool_descriptions.py`, `agent/mcp_server.py` (the 11 tools; `tracegraph-mcp` serves them over stdio for Claude Desktop), `agent/assembly.py`, `agent/prompts.py`, `agent/planner.py`, `agent/loop.py` (`BuyerAgent`), `agent/runs.py`, `agent/narration.py`, `agent/citations.py` (L5).
- `graph/connection.py` now checks the port before opening the client and puts a time limit on every call. Found while testing: the FalkorDB client waits minutes on a stopped server, which would have made "pull the plug" hang.
- Checked: the MCP server lists exactly 11 tools, each with a description; with FalkorDB off, `trace_score` and `hire_with_escrow` both refuse. Unit tests for the meter maths, endpoint choice, response parsing, replay order, the planner, the citation regex, receipt narration and memory carry-over.
- Open, FalkorDB checks: `tests/agent/test_agent_in_falkordb.py` drives the real loop with a rule-following stand-in for the LLM. Expected: Buyer 1's summarise job goes recall, score (flagged), funding_path plus find_ring, quarantine, rescore, hire an honest provider, settle (released), write_lesson, and the narration passes the citation check. Then Buyer 3's translate job sees TransFast excluded as quarantined without investigating.
- Open: one live run against GitHub Models to confirm the real model follows the flagged path (this is what the L2 eval in phase 10 measures).

### Phase 9, scoreboard
- `eval/contract.py` (the paper's Section 7.3 contract and a frozen settings hash), `eval/lanes.py`, `eval/population.py`, `eval/ledger.py`, `eval/choosing.py`, `eval/attackers.py`, `eval/outcomes.py`, `eval/investigator.py` (the flagged-case path, scripted: `funding_path`, `find_ring`, `quarantine` through the same `InvestigationCase` the agent uses), `eval/market_run.py`, `eval/summary.py` (mean, se, median, p90, max, the demo-seed rule), `eval/runner.py` (worker processes), `eval/cli.py` (`tracegraph-scoreboard`), `graph/queries/scoreboard.py`.
- The guard is now one Cypher fragment, `report_guard`, shared by the agents' evidence query and the scoreboard's round read.
- PPR now runs as a weighted matrix walk (numpy). Same maths; the JS parity test still matches to 1e-9.
- No LLM is called anywhere in the scoreboard.
- Checked: 19 unit tests (contract, frozen hash, market draws, outcome rules, delay, ignored claims, greedy ties, investigation trigger, percentiles, demo seed, guard behaviour per lane).
- Dry run in memory (Python reference of the guard, not FalkorDB), strat, 10 seeds, mean fraud in sats: alone 142.6, together 50.6, poisoned 157.8 (max 1,226), guarded 68.9, half hidden 171.8, bad-mouthed 220.4. Calib: alone 180.7, together 67.2, poisoned 156.1. Same direction as spikes X5 and X6. These are not the scoreboard numbers; the real run is in FalkorDB.
- Speed: 0.1 to 0.4 s of Python per market, so 1,400 markets (7 lanes, 2 adversaries, 100 seeds) take a few minutes across worker processes, plus FalkorDB time.
- Open, FalkorDB checks: `tests/eval/test_scoreboard_in_falkordb.py` (Cypher guard gives the same markets as the reference on 4 lanes; the quarantine lane blocks exactly the ring; lane graphs are deleted). Then the full 100-seed run.

### Phase 10, agent evals
- `eval/agent_cases.py` (100 labelled cases), `eval/case_market.py` (a case as a market graph), `eval/stand_ins.py` (no-LLM provider work and judge), `eval/text_lane.py` (the same model reading reviews as plain text), `eval/graph_lane.py` (the buyer agent with the FalkorDB tools, one graph per case), `eval/case_runs.py`, `eval/agent_scores.py` (L1, L2, citation pass rate), `eval/agent_eval.py`, `eval/agent_cli.py` (`tracegraph-agent-eval`), `graph/queries/agent_eval.py` (results stored in the `ops` graph).
- `BuyerAgent.run_plan` split out of `run_task`, so a fixed plan can run without the planner; `build_marketplace` takes any provider list; the citation check knows `writer-` ids.
- Checked: TRACE gives every case the status its label implies (100 cases). Unit tests for the stand-in judge (passes real work, fails the scam's canned output), the text lane (sees every review, never sees funding), scam accounting and the L1/L2 maths.
- Open: `tests/eval/test_agent_eval_in_falkordb.py` (a ring case is investigated, quarantined and paid honestly; a clean case is paid with no investigation). Then the live run: `tracegraph-agent-eval --cases 100`. Estimated cost on the paid key, if the free endpoint is rate-limited: about 25k input tokens per graph case and 1.5k per text case, roughly $0.40 for all 100. The meter still stops paid use at $1.80.

### Phase 11, HTTP API
- `api/server.py` (`create_app`, `tracegraph-api`), `api/state.py`, `api/task_runs.py` (tasks run in the background; their events are kept and streamed), `api/schemas.py`, and routes in `api/routes/`: `ops.py` (`/health`, `/llm/spend`, `/profile/trace-score`), `tasks.py` (`POST /tasks`, `/tasks/{id}`, `/tasks/{id}/events` as server-sent events), `graph_views.py` (snapshot, receipt, who-authorised, job, funding, neighbourhood), `investigator.py` (`POST /investigator/ask`), `scoreboard.py` (`/scoreboard`, `/evals/agent`, `/scoreboard/live`), `admin.py` (seed, ring, guard, plug; token required).
- The L3 investigator: `agent/investigator.py`, `agent/investigator_server.py` (six read-only MCP tools then, eight since Oct 18), `agent/tools/views.py`, `graph/queries/views.py`. `agent/mcp_calls.py` holds the MCP helpers the buyer loop and the investigator share.
- Core changes the API needed: the demo seed splits into `honest_market` and `ring_arrival` (`tracegraph-seed --no-ring`, `POST /admin/ring`); guard mode `unguarded` for the Poison button; `GraphDatabase.unplugged`; `MarketRun` reports each round (`on_round`, `fraud_by_round`) and takes a `graph_tag` so live runs never share graphs; the buyer's MCP tools can also be served over HTTP at `/mcp` (`MCP_OVER_HTTP=true`).
- Checked without FalkorDB: health fails closed (503), every graph read with the database down is a 503, admin needs the token and is off without one, the plug switch, input validation, a task with the database down is refused with a 503 before it starts (since Oct 18, when task numbering began reading the graph), the live lane streams an `error` event and is capped at two, MCP over HTTP answers `initialize`, OpenAPI builds (23 routes since Oct 18), the investigator has exactly eight read-only tools.
- Open: `tests/api/test_api_in_falkordb.py` (ring arrives on demand, the investigator follows the funding chain and the visitor cap returns 429, receipts 404 for unknown ids, the profile returns a plan).

### Phase 12, docs
- `README.md`: what it is, tracks, setup, the graph data model (labels, relationships, named graphs, indexes), the key Cypher and algorithms, the removal test, the API table, prior own work (TRACE and SatsRouter), data. No AI-use section: Nikunj writes that one.
- `docs/QUERIES.md` is generated by `tools/write_queries_doc.py` from the `Query` objects; `check.sh` fails when it is stale. `docs/ARCHITECTURE.md`: the picture, one job step by step, packages, where state lives, fail closed, the scoreboard.
- `agent/tools/looking.py` renamed to `agent/tools/views.py` so it is not confused with `lookups.py`; `count_question` moved to `graph/queries/ops.py` because it writes; the eval commands got `--help` text.
- Open: the README results section, filled from the 100-seed scoreboard and the 100-case agent eval once FalkorDB runs.

### Addition after phase 12: the what-if receipt (D37)
- `evidence/what_if.py`, `evidence/what_if_text.py`, `graph/queries/what_if.py`; `$as_of` on the evidence query (`EvidenceRequest.as_of`); `explaining.what_if`; `GET /decisions/{id}/what-if`; the investigator's seventh tool; `GuardMode` moved to `evidence/rules.py`.
- Checked without FalkorDB: shift detection (a gain without a flip, and a flip) and the sentence in each case. Python TRACE on the demo market: the guard off moves prov-quickdigest from -0.28 to 0.08 and prov-tagstar the same, while the top picks hold.
- Open: `tests/evidence/test_what_if_in_falkordb.py` (replay matches the record, 20 newly counted reviews from writers sharing root-ring-hub, later reviews do not leak in, unknown decisions refused).


### Addition: running on the FalkorDB Cloud free tier (D38)
- `eval/saved_results.py` (`keep_copy`, `restore_saved_results`); `save_scoreboard` and `save_agent_eval` write `results/scoreboard.json` and `results/agent-eval.json` before storing; both save queries skip a run id already in the graph; `tracegraph-seed` and `POST /admin/seed` store the kept runs again; `results/` is no longer ignored.
- `UdfRejectedError` when the server refuses the TRACE UDF; `seed_demo_market(..., with_udf=...)` skips the UDF when `SCORER=python`.
- `eval/checkpoint.py`: the scoreboard resumes from `results/scoreboard-progress.jsonl` after a restart; `run_all` cancels queued markets on a failure.
- Reads on a graph that does not exist yet return no rows (`GraphDatabase.run`), and the spend meter treats that as $0.
- Checked on FalkorDB Cloud (v4.22.0, AWS ap-south-1): every test, including the 32 database tests. The save queries' "skip if stored" guard was rewritten after the first run showed `WITH old WHERE old IS NULL` letting a duplicate through.

### Addition: the site (D40) and fixes found while building it (Oct 18)
- `web/`: Vite, React 18 and TypeScript; `api/` (typed client, server-sent events for tasks and live lanes), `graph/` (d3-force layout on a canvas, highlights, labels that skip collisions), `agent/` (tool trace state, highlights, one-line summaries), `sections/` (hero, agent console, ring, receipts, proof, investigator, pull the plug, footer). `npm run build` writes `web/dist`, which the API serves at `/`.
- Backend changes the site needed: `GET /jobs` and `GET /quarantines`; `quarantines` as the investigator's eighth tool; `hire_with_escrow` returns the provider's name; `write_lesson` accepts payment and job ids as evidence; task numbers come from the graph (D41).
- Found in the browser and fixed: narration ids with an underscore (`dec-task-2-extract_keywords-1`) were cut at the underscore and reported as unknown by the citation check (`agent/citations.py`, with a test). The L2 eval used only summarise jobs, so its 100% citation figure is unchanged.
- Checked: `./check.sh` (279 tests, every database test on FalkorDB Cloud), `tsc -b`, `npm run build`, a live task, the receipts, the race, one investigator question, the page at 1440 and 390 pixels wide with no sideways scroll, and the API serving `web/dist`.

### Addition: design pass on the site (Oct 18)
- Header: the hackathon name and track badges are gone from the top bar; the footer still credits Graph Hacks.
- Fixes: the page opened scrolled down because the tool trace scrolled the window, so it now scrolls only its own box; a failed snapshot shows the error and a retry instead of an empty stage; the market reloads when FalkorDB comes back.
- Layout: Rings, Proof and Unplug open with a centred statement heading. The ring section moved to `sections/ring/` and is one wide graph above five steps (shortest path, WCC and label propagation, PageRank, betweenness, quarantine); pointing at a step lights what it found. Proof leads with the two scam counts side by side, then a table of how the graph lane used its tools, then the race. The race runs in two heats of two lanes, because four live lanes at once crashed the free tier (D38), and ends with a two-sentence verdict.
- Type: one fewer heading size, 14px for descriptive text, readable line lengths on receipts and the footer.
- Graph: the hero tints the caught ring and its `MEMBER` nodes orange and labels only buyers and providers; labels no longer cover nodes. The console graph, before a task, lights the chosen buyer and its neighbours.
- Words: buyers and providers appear by name everywhere (ranking, receipts, ledger, the guard-off sentence), with the id kept as a tooltip. "LCB" is now "Worst case"; "scorer udf" is "scored inside FalkorDB"; receipt titles read "Extract keywords by Keyword Co" with the prompt quoted under them.
- Operator controls (guard switch, unplug) only show with `?operator` in the address (D42).
- Checked: `tsc -b`, `npm run build`, the design detector with no findings, and the page at 1536 and 390 pixels wide.
