import re
from dataclasses import dataclass, field

from tracegraph.graph.connection import GraphDatabase, GraphTimer
from tracegraph.graph.queries.receipts import KNOWN_IDS

ID_PATTERN = re.compile(
    r"\b(?:prov|buyer|sybil|writer|dec|job|pay|policy|ring|lesson|task|root|wallet|principal)"
    r"-[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]"
)


@dataclass
class CitationCheck:
    cited: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    retried: bool = False
    fell_back_to_receipt: bool = False

    # True when every id the text cites is a real node
    @property
    def passed(self) -> bool:
        return not self.unknown


# Every node id mentioned in a piece of text, in order, each once
def cited_ids(text: str) -> list[str]:
    return list(dict.fromkeys(ID_PATTERN.findall(text)))


# Checks every id a narration cites against the graph
async def check_citations(
    database: GraphDatabase, graph_name: str, text: str, timer: GraphTimer | None = None
) -> CitationCheck:
    cited = cited_ids(text)
    if not cited:
        return CitationCheck()
    rows = await database.rows(graph_name, KNOWN_IDS, {"ids": cited}, timer)
    known = {str(row["id"]) for row in rows}
    return CitationCheck(
        cited=cited, unknown=[node_id for node_id in cited if node_id not in known]
    )
