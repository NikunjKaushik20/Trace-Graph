from tracegraph.graph.queries.query import Query

RECORD_FUNDING_TRACE = Query(
    name="record_funding_trace",
    purpose="Notes on the decision that the agent traced the money from a writer to a provider.",
    read_only=False,
    text="""
MATCH (decision:Decision {id: $decision_id})
MATCH (provider:Provider {id: $provider_id})
CREATE (decision)-[:TRACED_FUNDING {
  writer_id: $writer_id,
  node_ids: $node_ids,
  hops: $hops,
  t: $t
}]->(provider)
""",
)

RECORD_RING = Query(
    name="record_ring",
    purpose=(
        "Stores a ring found by find_ring, with MEMBER edges to its providers, writers and "
        "wallets, and links the decision that investigated it."
    ),
    read_only=False,
    text="""
MATCH (decision:Decision {id: $decision_id})
MERGE (ring:Ring {id: $ring_id})
ON CREATE SET ring.hub_id = $hub_id,
              ring.bridge_id = $bridge_id,
              ring.size = size($member_ids),
              ring.found_at = $t
CREATE (decision)-[:INVESTIGATED {t: $t}]->(ring)
WITH ring
UNWIND $member_ids AS member_id
OPTIONAL MATCH (writer:Writer {id: member_id})
OPTIONAL MATCH (provider:Provider {id: member_id})
OPTIONAL MATCH (wallet:Wallet {id: member_id})
WITH ring, coalesce(writer, provider, wallet) AS member
WHERE member IS NOT NULL
MERGE (ring)-[:MEMBER]->(member)
""",
)

QUARANTINE_RING = Query(
    name="quarantine_ring",
    purpose=(
        "Writes a quarantine Policy covering every provider in a ring. Only works when the same "
        "decision both investigated the ring and found a funding path into it."
    ),
    read_only=False,
    text="""
MATCH (decision:Decision {id: $decision_id})-[:INVESTIGATED]->(ring:Ring {id: $ring_id})
MATCH (decision)-[trace:TRACED_FUNDING]->(traced:Provider)<-[:MEMBER]-(ring)
WHERE trace.hops > 0
WITH decision, ring, count(traced) AS traced_into_ring
WHERE traced_into_ring > 0
CREATE (policy:Policy {
  id: $policy_id,
  kind: 'quarantine',
  reason: $reason,
  created_by: decision.buyer_id,
  created_at: $t
})
CREATE (policy)-[:JUSTIFIED_BY]->(decision)
CREATE (policy)-[:TARGETS]->(ring)
WITH policy, ring
MATCH (ring)-[:MEMBER]->(provider:Provider)
CREATE (policy)-[:COVERS]->(provider)
RETURN policy.id AS policy_id, policy.created_by AS created_by, collect(provider.id) AS covered
""",
)

ACTIVE_POLICIES = Query(
    name="active_policies",
    purpose="Every quarantine in force, with who wrote it, why, and which providers it covers.",
    text="""
MATCH (policy:Policy {kind: 'quarantine'})-[:COVERS]->(provider:Provider)
OPTIONAL MATCH (policy)-[:JUSTIFIED_BY]->(decision:Decision)
RETURN policy.id AS policy_id,
       policy.reason AS reason,
       policy.created_by AS created_by,
       policy.created_at AS created_at,
       decision.id AS decision_id,
       collect(provider.id) AS covered
ORDER BY created_at
""",
)
