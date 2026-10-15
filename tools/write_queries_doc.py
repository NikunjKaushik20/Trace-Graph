import importlib
import pkgutil
import sys
from pathlib import Path

import tracegraph.graph.queries as queries_package
from tracegraph.graph.queries.query import Query

DOC_PATH = Path("docs/QUERIES.md")

SECTIONS = {
    "market_setup": "Writing the market",
    "catalogue": "Finding providers and jobs",
    "evidence": "Evidence, the write guard and TRACE scoring",
    "decisions": "Recording decisions",
    "jobs": "Tasks, hiring, escrow and settlement",
    "outcomes": "Outcomes",
    "investigation": "Following the money and finding rings",
    "policies": "Quarantine",
    "memory": "Lessons and memory recall",
    "receipts": "Receipts and accountability",
    "what_if": "What if: replaying a decision with another guard",
    "views": "Read-only views for the API and the investigator",
    "scoreboard": "Scoreboard",
    "agent_eval": "Agent evals",
    "ops": "Operations",
}

INTRO = """# Cypher queries

Every query the backend sends to FalkorDB, generated from the `Query` objects in
`src/tracegraph/graph/queries/` by `tools/write_queries_doc.py`. The quality gate fails if this
file is out of date. Read-only queries run with `GRAPH.RO_QUERY`.

Graph algorithms used: `algo.SPpaths` (funding path), `algo.WCC` (funding components),
`algo.labelPropagation` (CDLP communities), `algo.pageRank` (funding hubs), `algo.betweenness`
(brokers), and the vector index `db.idx.vector.queryNodes` (memory recall). TRACE scoring runs
inside FalkorDB as the JavaScript UDF library in `src/tracegraph/graph/udf/trace_score.js`,
called from `trace_scores` below.
"""


# Every Query defined in one module, in the order the module defines them
def queries_in(module_name: str) -> list[Query]:
    module = importlib.import_module(f"{queries_package.__name__}.{module_name}")
    found = [value for value in vars(module).values() if isinstance(value, Query)]
    return [query for query in found if query_home(module, query)]


# True when the query was defined in this module, not imported into it
def query_home(module: object, query: Query) -> bool:
    source = Path(str(getattr(module, "__file__", ""))).read_text(encoding="utf-8")
    return f'name="{query.name}"' in source


# One query as a Markdown section
def query_section(query: Query) -> str:
    mode = "read-only" if query.read_only else "writes"
    return (
        f"### `{query.name}` ({mode})\n\n{query.purpose}\n\n```cypher\n{query.text.strip()}\n```\n"
    )


# The whole document, one section per query module
def queries_doc() -> str:
    modules = [info.name for info in pkgutil.iter_modules(queries_package.__path__)]
    unknown = sorted(set(modules) - set(SECTIONS) - {"query"})
    if unknown:
        raise SystemExit(f"add a section title for: {', '.join(unknown)}")
    parts = [INTRO]
    for module_name, title in SECTIONS.items():
        parts.append(f"## {title}\n")
        parts.extend(query_section(query) for query in queries_in(module_name))
    return "\n".join(parts)


# Writes docs/QUERIES.md, or with --check fails when the file on disk is stale
def main() -> None:
    text = queries_doc()
    if "--check" in sys.argv:
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if current != text:
            raise SystemExit("docs/QUERIES.md is out of date: run tools/write_queries_doc.py")
        return
    DOC_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {DOC_PATH}")


if __name__ == "__main__":
    main()
