# Deviations from IDEA.md

Every place the backend differs from `nikunj/IDEA.md`. Each entry says what IDEA.md asked for, what we built, why it is better, and how to go back.

## D1. The trust score runs inside FalkorDB

- **IDEA.md:** TRACE scoring computed from Cypher reads, with PPR as a client-side power iteration.
- **Built:** the TRACE utility, including personalized PageRank from the admitted buyers, is a JavaScript UDF library loaded into FalkorDB (`Trace.scoreCandidates`, in `graph/udf/trace_score.js`). The `trace_scores` query gathers the guarded evidence with Cypher and hands it to the UDF, so one query returns a score for every candidate. A Python copy of the same maths runs the 100-seed scoreboard. `tests/trace/test_udf_parity.py` runs the real JS file under Node on 12 random markets and checks every field matches Python to 1e-9.
- **How the UDF gets its input:** Cypher does the guard (admission, `FUNDED_BY*1..3`), and the UDF does the maths on the lists Cypher collects. The UDF does not walk nodes itself with `getNeighbors`. That keeps one copy of the guard, written in Cypher where a judge can read it, and keeps the JS a plain function of its inputs, which is what makes the parity test possible.
- **Why better:** the decision is made by the graph, in the graph. "Is FalkorDB really deciding?" has a one-query answer. It also closes the gap that FalkorDB has no native personalized PageRank.
- **Undo:** set `SCORER=python` and the agent uses the Python scorer.
- **Status:** approved by Nikunj (upgrade 1).

## D2. Alone and Together are separate named graphs

- **IDEA.md:** partitioned vs shared is one Cypher clause, `WHERE r.writer = $me`.
- **Built:** in the Alone view each buyer reads and writes its own named graph (`market:private:<buyer>`). In the Together view all buyers use `market`. The scoreboard gives each lane and seed its own graph.
- **Why better:** the paper's partitioned view becomes FalkorDB's multi-graph feature, which the sponsor names as a headline. Eval runs are isolated and can run side by side.
- **Undo:** point every buyer at `market` and filter by writer.
- **Status:** approved by Nikunj (upgrade 2).

## D3. Memory recall uses a vector index plus the graph

- **IDEA.md:** `recall_memory` returns past decisions, pooled trust and policies.
- **Built:** the same, plus lessons are embedded with a local model (`BAAI/bge-small-en-v1.5`, 384 dimensions) into a FalkorDB vector index. Recall is one query: lessons close to the task, ranked up when they are about today's candidates.
- **Why better:** semantic memory the agent can search, not only a log it scans.
- **Undo:** drop the vector index; recall falls back to the newest lessons.
- **Status:** approved by Nikunj (upgrade 3).

## D4. `find_ring` also uses betweenness

- **IDEA.md:** WCC, CDLP and PageRank.
- **Built:** adds `algo.betweenness` to name the broker nodes that connect the ring to honest buyers.
- **Why better:** one more native algorithm the agent uses for a real question.
- **Undo:** remove the betweenness step from `find_ring`.
- **Status:** approved by Nikunj (upgrade 4).

## D5. Query timings are part of every tool result

- **IDEA.md:** the scoreboard logs ms per `trace_score` call.
- **Built:** every tool result carries the FalkorDB run time of its queries, and `/profile` returns `GRAPH.PROFILE` output for the main queries.
- **Why better:** shows the sponsor's speed claim on each agent step.
- **Undo:** drop the `graph_ms` field.
- **Status:** approved by Nikunj (upgrade 5).

## Logged during the build

### D6. Test functions carry no comment line

- **Rule asked for:** a one-line comment above every function.
- **Built:** test functions are named as sentences and have no comment; test helpers do have one.
- **Why better:** `# Checks a proven provider beats a newcomer` above `test_proven_provider_beats_a_newcomer` says the same thing twice.
- **Undo:** add a comment above each test.

### D7. One evidence query instead of four

- **Plan before the build:** separate reads for reports, provider activity, reviewer funders and admitted buyers.
- **Built:** one query, `candidate_evidence`, made of four named Cypher parts (`CANDIDATE_PROVIDERS`, `GUARDED_REPORTS`, `REVIEWER_FUNDERS`, `SEED_WRITERS`). `trace_scores` is the same four parts with the UDF call at the end.
- **Why better:** one round trip per decision instead of four, and the Python and in-database scorers read exactly the same evidence, so a parity failure can only come from the maths.
- **Undo:** split the parts back into four queries.

### D8. Reports are put in a fixed order before scoring

- **IDEA.md:** silent on ordering.
- **Built:** both scorers sort reports by time, then writer id, then job id before computing smoothed risk and CUSUM.
- **Why better:** risk and CUSUM depend on order. Without a fixed order, two reports in the same round could be read in either order and the same graph could give two different scores.
- **Undo:** none needed; it only removes randomness.

### D9. Buyers also carry the `:Writer` label

- **IDEA.md:** `(:Buyer|:Writer)-[:REPORTED]->(:Provider)`.
- **Built:** every node that can write a report is a `:Writer`; admitted buyers are `:Writer:Buyer`. The guard still asks `writer:Buyer AND writer.admitted`.
- **Why better:** "find the writer with this id" becomes one indexed lookup, `MATCH (w:Writer {id: $id})`. Without it, matching "a Buyer or a Writer" scans every node per row, which the 1,000-provider scoreboard would feel.
- **Undo:** drop the extra label and match on both labels.

### D10. Payments are nodes, not a `PAID` edge

- **IDEA.md:** `(:Buyer)-[:PAID {sats,t,status}]->(:Job)` and also `(:Payment)-[:FOR_DECISION]->(:Decision)`.
- **Built:** one `:Payment {sats, status, invoice_id, payment_hash}` node, `(:Writer)-[:MADE]->(:Payment)-[:FOR_JOB]->(:Job)` and `(:Payment)-[:FOR_DECISION]->(:Decision)`.
- **Why better:** IDEA.md's model needs a payment to point at a decision, and an edge cannot have edges. One node holds both, so there is one source of truth for escrow status and `who_authorised` is a plain path: Payment, Decision, Job, Task, Buyer, Principal.
- **Undo:** none planned; the PAID edge would duplicate the node.

### D11. Flags cover every provider the buyer may hire, not only the top pick

- **IDEA.md:** `trace_score` returns `confident` or `flagged` with reasons; the demo beat has a cheap provider with 20 fake reviews flagged, investigated, quarantined, and "the honest provider hired instead".
- **Built:** flags are computed for each provider in the hireable set (top 3) and returned per provider. The decision is `flagged` if any of them is flagged. "Close call" stays on the top pick.
- **Why better:** under the closed-fleet guard the fake praise is not counted, so the ring provider never ranks first. With top-pick-only flags the beat in IDEA.md section 8 could not happen in the default mode. Now the agent sees "QuickDigest: 20 reports from uncounted writers" while it is still a candidate it could pay.
- **Undo:** set the hireable count to 1 for flagging.

### D12. `settle` runs the judge itself

- **IDEA.md:** `settle(job, verdict)`.
- **Built:** `settle(job)`. The tool calls the judge (schema check, then LLM check) and settles by its verdict.
- **Why better:** if the agent passed the verdict in, a talked-into-it LLM could release a scammer's payment. Same reasoning as the top-3 rule on `hire_with_escrow`.
- **Undo:** add a verdict argument.

### D13. Two extra hire checks

- **IDEA.md:** `hire_with_escrow` checks the Policy filter and the ranked set.
- **Built:** also refuses when the provider's invoice asks for more than its listed price, or when the buyer cannot afford the job. Both checks run in Python for a clear reason and again inside the `hold_payment` Cypher.
- **Why better:** a scammer could otherwise list cheap and invoice high.
- **Undo:** remove the two checks.

### D14. More folders than the approved layout

- **Approved layout:** `config`, `graph`, `trace`, `market`, `agent`, `eval`, `api`.
- **Built:** also `evidence/` (the guard rules, the evidence reader, the scorer switch, decision records), `investigation/`, `memory/` and `llm/`.
- **Why better:** the guard is the project's main idea and gets its own folder instead of hiding inside `trace/` (pure maths) or `market/` (money). Each folder keeps one job, so files stay small.
- **Undo:** merge `evidence/` into `trace/`.

### D15. WCC runs over funding links only; CDLP runs over funding and praise

- **IDEA.md:** `find_ring` runs WCC and CDLP "over the FUNDED_BY plus REPORTED subgraph around the provider", then PageRank names the hub funder.
- **Built:** WCC over `FUNDED_BY` only decides who is in the ring. CDLP over `FUNDED_BY` and `REPORTED` together is returned beside it as the praise community. PageRank over `FUNDED_BY` names the hub; betweenness (D4) names the bridge wallet. A ring is called only when the funding component holds more than the provider and outside (not admitted) writers in it praised providers in it.
- **Why better:** WCC treats any edge as a join. One honest buyer that once paid a ring provider would put every honest buyer and provider into the ring's component. Money ties cannot be made by accident, so they draw the boundary, and the praise view backs it up.
- **Undo:** add `REPORTED` to the WCC relationship list.

### D16. Quarantine needs a funding path that actually reaches the ring

- **IDEA.md:** `quarantine` requires a `find_ring` result and a `funding_path` in the same Decision.
- **Built:** the same, checked inside the `quarantine_ring` Cypher, with one tightening: the traced path must have at least one hop and end at a provider that is a member of the ring. Every `funding_path` call is still written onto the decision, including ones that find nothing, so the receipt shows "checked, no shared funding".
- **Why better:** otherwise an agent could trace an honest buyer (no path) and still pass the check.
- **Undo:** drop `WHERE trace.hops > 0`.

### D17. Lessons are checked before they are saved, and shared between buyers

- **IDEA.md:** `write_lesson(text, evidence_ids)` links a Lesson to the decisions and paths behind it; `recall_memory` returns lessons next session.
- **Built:** `write_lesson` refuses a lesson that cites an id the graph does not have, or that cites no Decision or Policy. Decisions and policies become `FROM` edges; providers and rings become `ABOUT` edges. Recall returns lessons written by any admitted buyer, each labelled with its author, and moves lessons about today's candidates to the front (a lesson about a ring counts when any ring member is a candidate).
- **Why better:** the L5 rule (no made-up citations) applies to memory too, so a lesson is always backed by a real decision. Sharing lessons is the Track 02 point: Buyer 3 benefits from what Buyer 1 learned. Lessons never change a score; TRACE still decides from counted evidence.
- **Undo:** filter recall to `author_id = buyer_id`.

### D18. Tool arguments name the job and the decision

- **IDEA.md:** `recall_memory(buyer)`, `trace_score(candidates)`, `funding_path(a, b)`, `find_ring(provider)`, `hire_with_escrow(provider, job)`, `quarantine(ring, reason)`.
- **Built:** `recall_memory(task_text)`, `trace_score(job_id)`, `funding_path(decision_id, writer_id, provider_id)`, `find_ring(decision_id, provider_id)`, `hire_with_escrow(job_id, provider_id)`, `quarantine(decision_id, ring_id, reason)`. The buyer comes from the session, never from an argument.
- **Why better:** each investigation step is written onto the decision it belongs to, which is what lets `quarantine` check "a `find_ring` and a `funding_path` in the same Decision" inside Cypher (IDEA.md's own rule). Taking the buyer from the session means one buyer's agent cannot read or spend as another. `recall_memory` takes the task text so the vector search has something to match lessons against.
- **Undo:** none needed; the names and order of the 11 tools are unchanged.

### D19. `trace_score` scores every provider for the job, not a list the LLM passes

- **IDEA.md:** `trace_score(candidates)`.
- **Built:** `trace_score(job_id)` reads the job's capability and scores every provider that offers it (minus quarantined ones). `find_providers` is still there for the agent to look around.
- **Why better:** if the LLM chose the candidate list it could leave out the best provider, or slip in one it was talked into. The safety rule in IDEA.md section 6 ("`hire_with_escrow` only accepts a provider from the graph's ranked set") only holds if the graph, not the LLM, decides who is in the ranked set.
- **Undo:** add an optional `provider_ids` filter.

### D20. Ids are built from the job, so a replayed run writes the same graph

- **IDEA.md:** silent on ids.
- **Built:** a payment is `pay-{job_id}`, a decision is `dec-{job_id}-{n}` (n counts re-scores of the same job, so the rescore after a quarantine is `-2`), a job is `{task_id}-{capability}`.
- **Why better:** seeded replay (F15) only reproduces a take if the tool arguments the LLM produced last time still point at real nodes. Random ids would differ on each run and every replayed call would miss. Readable ids also make the receipts and the narration easy to follow on video.
- **Undo:** switch to uuid4 and drop replay.

### D21. Replay is recorded per channel

- **IDEA.md:** "seeded runs plus replay mode".
- **Built:** `LLM_MODE=record` saves every LLM reply in order, one list per channel (`buyer-1`, `judge`, `provider:prov-summa` and so on; a buyer's planner call goes on its own channel). `LLM_MODE=replay` plays each channel back in order and makes no network calls. Live calls use temperature 0 and a fixed seed.
- **Why better:** five buyers run at once, so a single global list would replay in a different order than it was recorded. Per-channel lists stay in step. Replay also costs nothing, so a judge can rerun the demo without touching the $2 budget.
- **Undo:** none needed.

### D22. The agent loop has two safety nets

- **IDEA.md:** "buyer loop with step cap 8".
- **Built:** the cap is 8 model turns per job. When it is reached, the model gets one more turn with no tools to write its summary. If a job ends with money still in escrow (cap hit, or the LLM went down mid-job), the loop calls `settle` itself so the judge decides and nothing is left held. Both are recorded on the run (`hit_step_cap`, `settled_by_safety_net`).
- **Why better:** without the second net, a held payment could sit in escrow forever, and a buyer's balance would look wrong on the scoreboard. The judge still makes the call, so the safety net never picks a winner.
- **Undo:** remove `left_in_escrow` from `loop.py`.

### D23. The planner falls back to keywords

- **IDEA.md:** "LLM plans sub-tasks".
- **Built:** the LLM plans first. If it is down or replies with something that is not the expected JSON, the task is split by keywords in the instruction part ("Summarise and translate: ...").
- **Why better:** the "pull the plug on the LLM" case still produces jobs, and a bad planner reply cannot invent a capability the market does not have (unknown ones are dropped).
- **Undo:** remove `jobs_from_keywords`.

### D24. Seven scoreboard lanes instead of six

- **IDEA.md:** "6 lanes incl. quarantine": partitioned, pooled, poisoned, guarded, bad-mouthed, quarantine.
- **Built:** the same six plus `guarded_half_hidden` (the funding check with half the Sybils hiding their funding link). The quarantine lane also runs with half hidden.
- **Why better:** IDEA.md puts this number on screen as an honest limit ("half-hidden funding is back to the no-sharing level") and answers judge question 2 with it. It should be measured by the build, not quoted from the spike. Running quarantine at half hidden is the case where the guard alone is weak, so it is the case where quarantine could matter.
- **Undo:** drop the lane from `eval/lanes.py`.

### D25. Fake praise is paid for

- **IDEA.md / spike X6:** 20 Sybil writers post 5 fake successes per round with no job behind them.
- **Built:** each fake success is a paid job: a Sybil pays a ring provider, which hands the money back to the ring. The attacker's spend is recorded.
- **Why better:** the build scores with all seven TRACE terms, and the edge-to-job term (weight 0.35) punishes reports with no paid job. Unpaid praise would be half-stopped by TRACE before the guard does anything, which would flatter the guard. A real attacker pays itself, as the demo roster's Sybils already do, so the scoreboard tests the guard against the stronger attack.
- **Undo:** use `record_unpaid_reports` in `eval/attackers.py`.

### D26. The scoreboard reads each report once

- **IDEA.md:** "one aggregate query per round, not per decision".
- **Built:** one Cypher read per round per graph returns only the reports written in the previous round, each already marked counted or ignored by the guard. The guard is the same Cypher fragment (`report_guard`) the agents' `candidate_evidence` uses. Python keeps the running evidence, applies the 2-round delay, and scores providers that nobody has reported on as one shared blank score (they are identical, so this gives the same ranking as scoring all 1,000).
- **Why better:** re-reading every report every round grows with the square of the run length and would not fit 100 seeds into the deadline. A test runs the same market through FalkorDB and through an in-memory reference of the guard and expects identical fraud.
- **Undo:** none needed.

### D27. Every lane on a seed gets the same prices and outcome draws

- **IDEA.md:** silent.
- **Built:** each seed pre-draws the job price and one random number per buyer per round, and the market (which providers are malicious, which are in the ring). Every lane on that seed uses the same draws.
- **Why better:** lane differences then come from the lanes, not from luck, so the paired gap between Alone and Together per seed (which the demo-seed rule uses) is meaningful.
- **Undo:** none needed.

### D28. In the agent evals, only the buyer uses the LLM

- **IDEA.md:** L1 runs "the same gpt-4o-mini" on 100 hiring cases with and without the graph; L2 scores the tool path on the same cases.
- **Built:** the buyer agent (graph lane) and the text-only buyer (text lane) both use gpt-4o-mini. The providers' work and the judge use stand-ins with no LLM: honest work is built from the input text, and the judge passes output that shares at least five long words with the input. The scam's canned output fails it. Each case runs as one summarise job, so the planner is skipped.
- **Why better:** L1 and L2 measure the buyer's decision, not the judge. Taking the other LLM calls out keeps the eval inside the $2 budget, and gives the same verdicts on every run.
- **Undo:** pass `ModelFactory` instead of `StandInModels` in `eval/graph_lane.py`.

### D29. L1 counts a scam as paid when it is hired

- **IDEA.md:** "Reported as scams paid and sats lost per lane".
- **Built:** a case counts as a scam paid when the agent hires a malicious provider, and the sats lost are that provider's price, even though the graph lane's escrow later refunds it.
- **Why better:** the text lane has no escrow. Counting refunds would credit the graph lane for the escrow, not for the decision, and the claim is about the decision. Refunds are still recorded in the graph for the receipts.
- **Undo:** none needed.

### D30. The case mix

- **IDEA.md:** "100 labelled cases: clean, suspicious-but-clean, ring", no mix given.
- **Built:** 40 clean, 30 suspicious-but-clean, 30 ring. Suspicious-but-clean comes in three kinds, 10 each: a cheap newcomer with one or two good jobs, two providers tied at the top, and a newcomer praised by outside writers with no money ties to it. Ring cases have 2 or 3 cheap scammers and outside praise funded from the same hub. A test runs the product's TRACE scorer on every case and checks it gets the status its label implies: clean is confident, and suspicious and ring are flagged.
- **Why better:** each suspicious kind trips a different flag, so L2 precision shows whether the agent follows the money only when there is money to follow. The outside-praise kind is the hard one: the praise is uncounted, so the agent may check it, and it should find no path and no ring.
- **Undo:** change `CASE_MIX` in `eval/agent_cases.py`.

### D31. More endpoints than the plan lists

- **IDEA.md:** the UI needs the tool trace, graph view, escrow states, the counter, receipt and pull the plug; Section 8 names no endpoints.
- **Built:** 23 routes. Beyond the obvious ones: `/jobs` and `/quarantines` (the receipts list and the ring panel, added Oct 18), `/jobs/{id}`, `/nodes/{id}/funding` and `/nodes/{id}/neighbourhood` (the same lookups the investigator uses, so a click in the graph view shows exactly what the agent would see), `/profile/trace-score` (FalkorDB's plan and timing for the scoring query, for the "Technical depth" criterion), `/llm/spend`, and `/scoreboard/live` (one lane on one seed played in FalkorDB, round by round, so the counter moves on screen instead of jumping to a stored number).
- **Why better:** every number on screen comes from a route that reads FalkorDB, and judges can call those routes directly.
- **Undo:** drop the routers from `api/server.py`.

### D32. The ring arrives mid-demo through an admin call

- **IDEA.md:** "catches a too-good-to-be-true provider" in the 0:55 beat; the seed included the ring from the start.
- **Built:** `tracegraph-seed --no-ring` writes the honest market only; `POST /admin/ring` adds the three ring providers, the 8 Sybil writers, their funding behind `root-ring-hub` and 20 fresh paid reviews each, to the shared graph and to every buyer's private copy. Without the flag, the seed is unchanged and all earlier tests still use it.
- **Why better:** in the video the scammer appears while the agent is working, which is the story, and the graph view shows the ring arriving.
- **Undo:** seed without `--no-ring`.

### D33. Pull the plug has a simulated switch as well as the real one

- **IDEA.md:** "Pull the plug: FalkorDB off, the agent refuses to pay."
- **Built:** `POST /admin/plug {"connected": false}` makes every database call raise `GraphUnavailableError`, exactly as when the server is gone, and `/health` says `unplugged: true`. Stopping the container (`docker compose stop falkordb`) does the same for real; the timeouts added in Phase 8 make that fail within 5 seconds instead of hanging.
- **Why better:** the live deploy can show the removal test to a judge without stopping a database that other visitors are using. The video uses the real stop.
- **Undo:** none needed; the switch is off by default and needs the admin token.

### D34. A third guard mode, `unguarded`, for the Poison button

- **IDEA.md:** "Press Poison: the Together counter overtakes Alone. Toggle Guard: the counter falls back."
- **Built:** the counter itself comes from the `poisoned` and `guarded` scoreboard lanes (stored and live). In addition, `POST /admin/guard` switches the live agents between `closed`, `open` and `unguarded`, so the same buttons can also poison the market the agent is reading.
- **Why better:** the agent demo and the scoreboard then tell the same story with the same guard code.
- **Undo:** leave the guard at `closed`.

### D35. The investigator gets eight read-only tools, not the agent's eleven

- **IDEA.md:** L3 "answers only through the typed tools and highlights the path it used. Capped at 10 questions per visitor and by the spend meter."
- **Built:** a separate MCP server with `recent_jobs`, `job_story`, `explain_decision`, `what_if` (D37), `who_authorised`, `funding_chain`, `neighbourhood` and `quarantines` (added on Oct 18, after a live question about why a provider was blocked had no tool to answer it). Every query behind them is marked read-only and runs with `ro_query`, so a visitor's question can never hire, pay or quarantine. The answer goes through the same citation check as the agent's, and `path_ids` lists every node the tools returned, for the UI to highlight. `recent_jobs` exists because ids are `task-14-summarise`, not "job 14": it lets the investigator find the job a question names loosely.
- **Why better:** a public text box in front of the money-moving tools would be a prompt-injection target. Read-only tools remove that risk completely.
- **Undo:** none recommended.

### D36. The visitor cap is counted in FalkorDB

- **IDEA.md:** "Capped at 10 questions per visitor".
- **Built:** each question runs one `MERGE (:Visitor {id})` with an increment in the `ops` graph before the LLM is called; question 11 gets a 429. The visitor is the `Visitor-Id` header the UI sends, or a hash of the address when there is none (the address itself is not stored). The cap is `INVESTIGATOR_QUESTIONS_PER_VISITOR`.
- **Why better:** the count survives restarts and works with more than one API worker, and the single-statement increment cannot be raced.
- **Undo:** none needed.

### D37. The "what if" receipt

- **IDEA.md:** the receipt lists the ignored claims and the funding path; the 30-second proof is the Poison and Guard buttons on the scoreboard counter.
- **Built:** `what_if(decision_id, guard)` replays a stored decision as of the moment it was made, once with the guard it used and once with another (`unguarded`, `open` or `closed`), and reports whether the pick changes, every provider whose score, place or counted reviews move, which writers and shared funders those reviews come from, and what the graph recorded about that provider afterwards (quarantines, failed paid jobs). It is served at `GET /decisions/{id}/what-if` and is the investigator's seventh tool. To replay faithfully, the evidence query takes an optional `$as_of` time: reports, payments and policies written after it are left out. Left empty, as in every live decision, the query behaves exactly as before.
- **Why better:** it shows what the write guard did to a real decision on the graph the agent used, with the same TRACE code. Replaying with the guard that was used also checks itself: `replay_matches_record` says whether it gives back the stored ranking.
- **Found while building it:** in the demo market as seeded, turning the guard off lifts the ring's providers (prov-quickdigest from -0.28 to 0.08) but does not put them first, because TRACE's own PPR distance and Sybil terms still hold them below the honest leaders (prov-summa 0.27). So the what-if says "the guard did not change this pick" and shows the jump. Funding links have no timestamps, so a replay treats them as always present.
- **Undo:** drop the route and the tool; `$as_of` is harmless left in.

### D38. FalkorDB Cloud free tier instead of the local container

- **IDEA.md:** FalkorDB v4.22.0 in Docker with AOF persistence, so evidence, results and memory survive restarts.
- **Built:** the deploy runs on the FalkorDB Cloud free tier (the sponsor's service; WSL and Docker are not available on our machine). That tier has 100 MB of memory, no persistence, no TLS, and stops an instance unused for a day. Three changes follow. The scoreboard and the agent eval write the exact parameters of their save query to `results/` before storing the run, and `tracegraph-seed` and `POST /admin/seed` store those files again; the save queries now start with `OPTIONAL MATCH (old {id: $run_id}) WITH count(old) AS already_stored WHERE already_stored = 0`, so storing a run twice is a no-op. (The usual `WITH old WHERE old IS NULL` lets a row through in FalkorDB 4.22 even when `old` exists; the test caught it.) `results/` is committed, not ignored. If the server refuses the TRACE UDF, `tracegraph-seed` says so and names the fix (`SCORER=python`), and with `SCORER=python` it no longer tries to load the UDF. The Docker setup is unchanged and still works locally.
- **Learned on the real instance (Oct 16):**
  - The instance restarted 4 minutes into the first scoreboard run (4 worker processes) and came back empty. The server process sits at about 60 MB resident even when empty, and each concurrent market adds a few MB that are not handed back, so 4 markets plus the demo market crossed the container's limit. The scoreboard now runs with 2 workers, writes every finished market to `results/scoreboard-progress.jsonl` (ignored by git, deleted after a successful save), and a rerun skips the markets already played under the same settings hash. A failed market cancels the queued ones instead of running them against a dead server.
  - A restart also forgets the TRACE UDF, and every `trace_score` then failed with "Unknown function 'Trace.scoreCandidates'" (caught after it wasted one eval run, about $0.07). Scoring now goes through `rows_with_trace_udf`, which loads the UDF again and retries once when the server has forgotten it, so live agents and evals recover from a restart by themselves.
  - FalkorDB refuses a read-only query on a graph that does not exist yet ("Invalid graph operation on empty key"). On a fresh instance that broke the spend meter, which is read before every LLM call. `GraphDatabase.run` now returns no rows for a read on a missing graph, and the meter reads no rows as nothing spent.
- **Why better:** the sponsor's own hosted service is the live deploy, and losing the instance no longer loses the 100-seed scoreboard, which takes over an hour to produce. Every number in the README is also in a file a judge can read without a database.
- **Cost:** a restarted free instance comes back empty until someone runs the seed. The live agents' decisions and lessons from before the restart are gone; the demo market and the eval results come back. The password is sent unencrypted, which is acceptable only because every record is synthetic.
- **Undo:** point `FALKORDB_URL` at the Docker container.

### D39. The scoreboard runs on GitHub Actions; CI runs every test against FalkorDB

- **IDEA.md:** the scoreboard runs against the project's FalkorDB and is stored there.
- **Built:** measured on the free instance with one worker, the server's resident memory reaches about 100 MB within two minutes of 1,000-provider markets, and the instance is restarted after about 14 of the 1,400. `.github/workflows/scoreboard.yml` runs `tracegraph-scoreboard` on a GitHub runner with `falkordb/falkordb:v4.22.0` as a service container and uploads `results/scoreboard.json`; `tracegraph-seed` then stores that run in the cloud instance (D38), where the API serves it. `.github/workflows/check.yml` runs `check.sh` on every push against the same image, so the database tests run in public, not only on our machine.
- **Why better:** the numbers come from the same code and the same FalkorDB version, on a machine with enough memory, and anyone can rerun them with one click. Shrinking the market to fit 100 MB would have broken the paper's Section 7.3 contract.
- **Cost:** the scoreboard is not computed on the hosted instance itself; it is stored there.
- **Undo:** run `tracegraph-scoreboard` against any FalkorDB with about 1 GB of memory.

### D40. The UI is one page served by the API

- **IDEA.md:** "One screen, one fraud counter, four states"; the UI shows the tool trace, graph view, escrow states, the counter, receipt and pull the plug (Section 8), and the funding path is "drawn in FalkorDB Browser".
- **Built:** `web/`, a React and TypeScript page built with Vite, in the sections the video follows: the live market graph, the agent console (task box, tool trace with FalkorDB time per call, graph view that lights up what each tool touched, escrow per job, narration with its citation check), the ring (funding path, writers, hub, bridge, policy, drawn from `/nodes/{id}/neighbourhood`), receipts with the what-if and authority chain, the proof (L1/L2 figures, the four-lane race played live through `/scoreboard/live`, the scoreboard), the investigator with its path drawn, and pull the plug with the operator buttons behind the admin token. The graph view is d3-force on a canvas, fed by `/graph/snapshot`. When `web/dist` exists, the API serves it at `/` (`WEB_DIR`). The race starts on the scoreboard's `demo_seed` and says so on screen ("One seed; the scoreboard has all 100"), as Section 8 asks.
- **Why better:** the path is drawn on the page the judge is already on, from the same routes the agent's tools read, instead of a switch to FalkorDB Browser. One process serves the site and the API, which keeps the free deploy to one URL and one service, with no CORS setup.
- **Cost:** one long page rather than one screen; the counter is in the proof section, not always in view. FalkorDB Browser still works for anyone who wants it.
- **Undo:** delete `web/` and the static mount in `api/server.py`.

### D41. Task numbers come from the graph

- **IDEA.md:** silent; the API counted tasks in memory.
- **Built:** `POST /tasks` reads every `Task` id from FalkorDB and takes the next number after the highest; an explicit `task_id` that is already taken gets a 409. Because it reads the graph first, a task with the database down is now refused with a 503 before it starts, instead of starting and failing on its first tool call.
- **Why better:** found on Oct 18 in the browser: after an API restart the counter began at `task-1` again, and the new task's jobs and decisions merged into the old task's nodes. A restart that forgets the counter can no longer overwrite a receipt.
- **Undo:** go back to an in-memory counter.

### D42. Operator controls are hidden from visitors

- **IDEA.md:** the video pulls the plug on FalkorDB from the page.
- **Built:** the guard switch and the unplug button still exist, and the admin token still guards them, but they only render when the address has `?operator`. Everyone else sees the state ("Payments allowed." or "Payments refused.") without the controls.
- **Why better:** a judge opening the public link should not land on a token field they cannot use. The demo recording opens `/?operator` and shows the same beat as before.
- **Undo:** drop the `OPERATOR` check in `sections/UnplugSection.tsx`.

## Questions for Nikunj

- **Q1. What are the γ and δ terms?** The paper (Section 3.2) says the two remaining graph signals are "PPR distance and counterparty entropy", so γ = 0.15 is a penalty on PPR distance and δ = 0.10 a bonus for entropy. SatsRouter's `config.ts` uses γ for cost and δ for network trust. We follow the paper. **Answered (Oct 15): keep the paper's meaning.**
