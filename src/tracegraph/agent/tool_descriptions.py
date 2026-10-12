RECALL_MEMORY = (
    "Call this first in every session. Returns what you remember from the shared graph: your "
    "past decisions and how they ended, pooled outcomes for providers you used, quarantines "
    "in force (written by you or other buyers), and lessons close to this task."
)

FIND_PROVIDERS = (
    "Lists providers that offer a capability (summarise, extract_keywords, translate), with "
    "prices. Quarantined providers are left out. Optional: trace_score already scores everyone."
)

TRACE_SCORE = (
    "Scores every provider for one of your jobs with TRACE from counted evidence in the graph, "
    "and records the decision. Returns decision_id, status, the hireable providers (top 3) with "
    "their flags, and who was excluded. If status is 'confident', hire the first hireable "
    "provider. If 'flagged', investigate the flagged providers before paying anyone."
)

FUNDING_PATH = (
    "Follows FUNDED_BY links between a writer and a provider (shortest path). Use it on a "
    "flagged provider with a writer from its uncounted_writers list. A path through a shared "
    "wallet means the praise was paid for by the provider's own money."
)

FIND_RING = (
    "Looks for a ring around a flagged provider: who shares its funding (WCC), who praises it "
    "(label propagation), the hub funder (PageRank) and the bridge wallet (betweenness). "
    "Returns ring_id when it finds one."
)

QUARANTINE = (
    "Quarantines every provider in a ring, for all buyers. Only works after find_ring returned "
    "that ring_id and funding_path found a path into it, both on the same decision. Give a "
    "one-sentence reason that names the evidence."
)

HIRE_WITH_ESCROW = (
    "Hires one of the hireable providers from the job's latest trace_score decision: pays its "
    "invoice into escrow and collects the work. The graph refuses providers outside the top 3 "
    "or under quarantine. Call settle next."
)

SETTLE = (
    "Has the judge check the work delivered for a job, then releases the escrow on a pass or "
    "refunds you on a fail. The outcome is written to the graph for every buyer to learn from."
)

WRITE_LESSON = (
    "Saves a short lesson for future sessions, after a refund or a quarantine. evidence_ids "
    "must be real ids from this session and include at least one decision_id or policy_id."
)

EXPLAIN_DECISION = (
    "Returns the receipt for a decision: the ranking, who was excluded and why, how many paid "
    "jobs were counted, which claims were ignored and why, the investigation, and the payment."
)

WHO_AUTHORISED = (
    "Shows who stands behind a payment: the principal that owns the buyer, the task, the job, "
    "the decision and the provider paid."
)

SERVER_INSTRUCTIONS = (
    "Tools for a buyer agent that hires and pays other agents. Every decision is made from the "
    "shared FalkorDB graph. You choose which tools to call; you cannot pay a provider the graph "
    "did not rank."
)

INVESTIGATOR_INSTRUCTIONS = (
    "Read-only tools over the TRACE-Graph market. They answer questions about jobs, decisions, "
    "payments and money; none of them changes anything."
)

JOB_STORY = (
    "One job from task to outcome: who asked for it, every decision made for it, the provider "
    "hired, the payment and how it ended, and the judge's reason. Start here for questions "
    "about a job, a refund or a payment."
)

RECENT_JOBS = (
    "The newest jobs with their task, provider and payment status. Pass payment_status "
    "'released' or 'refunded' to see only those. Use it to find a job the question names "
    "loosely, such as 'job 14' (task-14) or 'the last refund'."
)

FUNDING_CHAIN = (
    "Who funds a node (a writer, provider or wallet), up to 3 hops, and who else those funders "
    "pay for. Use it for questions like 'who funds provider X' or 'are these writers linked'."
)

QUARANTINES = (
    "Every quarantine in force: the policy id, the reason, the buyer that wrote it, the decision "
    "that justified it and the providers it covers. Pass provider_id to see only the ones "
    "covering that provider. Use it for 'why was X quarantined' or 'who blocked X'."
)

NEIGHBOURHOOD = (
    "The nodes and edges within 1 or 2 hops of a node. Use it to see what a node is connected "
    "to when no other tool fits."
)

WHAT_IF = (
    "Replays a stored decision as of the moment it was made, with a different write guard: "
    "'unguarded' counts every review, 'open' counts outside reviews unless the money links "
    "them, 'closed' counts only the fleet's own. Says whether the pick would change, which "
    "provider gains most, from which writers and funders, and what happened to it since. "
    "Use it for questions like 'what would have happened without the guard?'."
)
