from tracegraph.graph.queries.query import Query

FUNDING_PATH = Query(
    name="funding_path",
    purpose=(
        "Shortest chain of FUNDED_BY links, in either direction, between a writer and a "
        "provider. A path through a shared wallet or root is the money behind the praise."
    ),
    text="""
MATCH (writer:Writer {id: $writer_id}), (provider:Provider {id: $provider_id})
CALL algo.SPpaths({
  sourceNode: writer,
  targetNode: provider,
  relTypes: ['FUNDED_BY'],
  relDirection: 'both',
  maxLen: $max_hops,
  pathCount: 1
})
YIELD path
RETURN [node IN nodes(path) | node.id] AS node_ids,
       [node IN nodes(path) | labels(node)] AS node_labels
""",
)

FUNDING_COMPONENT = Query(
    name="funding_component",
    purpose=(
        "Weakly connected components (WCC) over FUNDED_BY: everyone who shares a funding tree "
        "with the provider. Money ties are the hard edge of a ring."
    ),
    text="""
CALL algo.WCC({nodeLabels: ['Writer', 'Provider', 'Wallet'], relationshipTypes: ['FUNDED_BY']})
YIELD node, componentId
WITH collect({id: node.id, labels: labels(node), component: componentId}) AS assignments
WITH assignments, [entry IN assignments WHERE entry.id = $provider_id][0].component AS target
RETURN [entry IN assignments WHERE entry.component = target | entry] AS members
""",
)

PRAISE_COMMUNITY = Query(
    name="praise_community",
    purpose=(
        "Community detection by label propagation (CDLP) over funding and reports together: "
        "the group the provider is praised and funded within."
    ),
    text="""
CALL algo.labelPropagation({
  nodeLabels: ['Writer', 'Provider', 'Wallet'],
  relationshipTypes: ['FUNDED_BY', 'REPORTED'],
  maxIterations: 20
})
YIELD node, communityId
WITH collect({id: node.id, community: communityId}) AS assignments
WITH assignments, [entry IN assignments WHERE entry.id = $provider_id][0].community AS target
RETURN [entry IN assignments WHERE entry.community = target | entry.id] AS community
""",
)

FUNDING_PAGERANK = Query(
    name="funding_pagerank",
    purpose="PageRank over FUNDED_BY: money flows up to funders, so the hub funder ranks first.",
    text="""
CALL algo.pageRank(null, 'FUNDED_BY')
YIELD node, score
WITH node, score
WHERE node.id IN $member_ids
RETURN node.id AS id, score
ORDER BY score DESC, id
""",
)

FUNDING_BETWEENNESS = Query(
    name="funding_betweenness",
    purpose="Betweenness over FUNDED_BY: the wallet most funding paths pass through.",
    text="""
CALL algo.betweenness({
  nodeLabels: ['Writer', 'Provider', 'Wallet'],
  relationshipTypes: ['FUNDED_BY']
})
YIELD node, score
WITH node, score
WHERE node.id IN $member_ids
RETURN node.id AS id, score
ORDER BY score DESC, id
""",
)

PRAISE_INSIDE = Query(
    name="praise_inside",
    purpose="Reports written by members of a funding component about providers in it.",
    text="""
MATCH (writer:Writer)-[report:REPORTED]->(provider:Provider)
WHERE writer.id IN $member_ids AND provider.id IN $member_ids
RETURN writer.id AS writer_id,
       coalesce(writer.admitted, false) AS admitted,
       provider.id AS provider_id,
       count(report) AS reports
""",
)
