from tracegraph.graph.queries.query import Query

CLASSIFY_EVIDENCE = Query(
    name="classify_evidence",
    purpose="Says what kind of node each id is, so a lesson can only cite things that exist.",
    text="""
UNWIND $ids AS id
OPTIONAL MATCH (decision:Decision {id: id})
OPTIONAL MATCH (policy:Policy {id: id})
OPTIONAL MATCH (provider:Provider {id: id})
OPTIONAL MATCH (ring:Ring {id: id})
OPTIONAL MATCH (payment:Payment {id: id})
OPTIONAL MATCH (job:Job {id: id})
RETURN id,
       CASE
         WHEN decision IS NOT NULL THEN 'Decision'
         WHEN policy IS NOT NULL THEN 'Policy'
         WHEN provider IS NOT NULL THEN 'Provider'
         WHEN ring IS NOT NULL THEN 'Ring'
         WHEN payment IS NOT NULL THEN 'Payment'
         WHEN job IS NOT NULL THEN 'Job'
         ELSE null
       END AS kind
""",
)

WRITE_LESSON = Query(
    name="write_lesson",
    purpose=(
        "Stores a lesson a buyer learned, embedded for vector search, linked FROM the decisions "
        "and policies that taught it and ABOUT the providers and rings it concerns."
    ),
    read_only=False,
    text="""
MATCH (buyer:Buyer {id: $buyer_id})
CREATE (buyer)-[:LEARNED]->(lesson:Lesson {
  id: $lesson_id,
  text: $text,
  created_at: $t,
  embedding: vecf32($embedding)
})
WITH lesson
OPTIONAL MATCH (decision:Decision) WHERE decision.id IN $source_ids
OPTIONAL MATCH (policy:Policy) WHERE policy.id IN $source_ids
OPTIONAL MATCH (provider:Provider) WHERE provider.id IN $subject_ids
OPTIONAL MATCH (ring:Ring) WHERE ring.id IN $subject_ids
WITH lesson,
     collect(DISTINCT decision) + collect(DISTINCT policy) AS sources,
     collect(DISTINCT provider) + collect(DISTINCT ring) AS subjects
FOREACH (source IN sources | CREATE (lesson)-[:FROM]->(source))
FOREACH (subject IN subjects | CREATE (lesson)-[:ABOUT]->(subject))
RETURN lesson.id AS lesson_id, size(sources) AS sources, size(subjects) AS subjects
""",
)

SIMILAR_LESSONS = Query(
    name="similar_lessons",
    purpose="Lessons closest to the task text, from the Lesson vector index, with what they cite.",
    text="""
CALL db.idx.vector.queryNodes('Lesson', 'embedding', $k, vecf32($query_vector))
YIELD node, score
OPTIONAL MATCH (author:Buyer)-[:LEARNED]->(node)
OPTIONAL MATCH (node)-[:FROM]->(source)
OPTIONAL MATCH (node)-[:ABOUT]->(subject)
OPTIONAL MATCH (node)-[:ABOUT]->(:Ring)-[:MEMBER]->(ring_provider:Provider)
RETURN node.id AS lesson_id,
       node.text AS text,
       node.created_at AS created_at,
       author.id AS author_id,
       score,
       collect(DISTINCT source.id) AS source_ids,
       collect(DISTINCT subject.id) AS subject_ids,
       collect(DISTINCT ring_provider.id) AS ring_provider_ids
ORDER BY score
""",
)

RECENT_LESSONS = Query(
    name="recent_lessons",
    purpose="The newest lessons, used when no embedding is available.",
    text="""
MATCH (author:Buyer)-[:LEARNED]->(node:Lesson)
OPTIONAL MATCH (node)-[:FROM]->(source)
OPTIONAL MATCH (node)-[:ABOUT]->(subject)
OPTIONAL MATCH (node)-[:ABOUT]->(:Ring)-[:MEMBER]->(ring_provider:Provider)
RETURN node.id AS lesson_id,
       node.text AS text,
       node.created_at AS created_at,
       author.id AS author_id,
       null AS score,
       collect(DISTINCT source.id) AS source_ids,
       collect(DISTINCT subject.id) AS subject_ids,
       collect(DISTINCT ring_provider.id) AS ring_provider_ids
ORDER BY created_at DESC
LIMIT $k
""",
)

PAST_DECISIONS = Query(
    name="past_decisions",
    purpose="A buyer's own recent decisions: what it needed, whom it chose, and how it ended.",
    text="""
MATCH (buyer:Buyer {id: $buyer_id})-[:RECEIVED]->(:Task)-[:SPLIT_INTO]->(job:Job)
      -[:DECIDED_BY]->(decision:Decision)
OPTIONAL MATCH (decision)-[:CHOSE]->(provider:Provider)
OPTIONAL MATCH (payment:Payment)-[:FOR_DECISION]->(decision)
RETURN decision.id AS decision_id,
       decision.created_at AS created_at,
       decision.status AS status,
       decision.flags AS flags,
       job.capability AS capability,
       provider.id AS provider_id,
       provider.name AS provider_name,
       payment.status AS payment_status,
       payment.sats AS sats,
       payment.verdict_reason AS verdict_reason
ORDER BY created_at DESC
LIMIT $limit
""",
)

POOLED_TRUST = Query(
    name="pooled_trust",
    purpose=(
        "For each provider this buyer has used: the outcomes every admitted buyer reported, "
        "pooled, and how many buyers they came from."
    ),
    text="""
MATCH (buyer:Buyer {id: $buyer_id})-[:REPORTED]->(provider:Provider)
WITH DISTINCT provider
MATCH (peer:Buyer)-[report:REPORTED]->(provider)
WHERE peer.admitted = true
RETURN provider.id AS provider_id,
       provider.name AS provider_name,
       provider.capability AS capability,
       count(CASE WHEN report.ok = true THEN 1 END) AS successes,
       count(CASE WHEN report.ok = false THEN 1 END) AS failures,
       count(DISTINCT peer) AS buyers
ORDER BY provider_id
""",
)
