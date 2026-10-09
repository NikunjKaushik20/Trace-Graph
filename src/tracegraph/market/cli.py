import argparse
import asyncio
import sys
import time

from tracegraph.config import get_settings
from tracegraph.eval.saved_results import restore_saved_results
from tracegraph.graph.connection import GraphDatabase, safe_address
from tracegraph.graph.udf_loader import UdfRejectedError
from tracegraph.market.seed import seed_demo_market

PYTHON_SCORER_HINT = "Set SCORER=python in .env to run TRACE in Python on the same graph evidence."


# Rebuilds the demo market, stores any kept eval results again, and prints what was written
async def seed_and_report(with_ring: bool) -> int:
    settings = get_settings()
    database = GraphDatabase(settings.falkordb_url)
    try:
        if not await database.is_reachable():
            print(
                f"FalkorDB is not reachable at {safe_address(settings.falkordb_url)}",
                file=sys.stderr,
            )
            return 1
        spec = await seed_demo_market(
            database,
            settings.shared_graph,
            settings.embedding_dimensions,
            time.time(),
            with_ring=with_ring,
            with_udf=settings.scorer == "udf",
        )
        restored = await restore_saved_results(database, settings)
    except UdfRejectedError as error:
        print(error, PYTHON_SCORER_HINT, sep="\n", file=sys.stderr)
        return 1
    finally:
        await database.close()
    print(
        f"Seeded '{settings.shared_graph}': {len(spec.providers)} providers, "
        f"{len(spec.buyers)} buyers, {len(spec.writers)} outside writers, "
        f"{len(spec.history)} past jobs, plus {len(spec.buyers)} private graphs."
    )
    if restored:
        print(f"Stored the kept results again: {', '.join(restored)}")
    return 0


# Entry point for the tracegraph-seed command
def seed_demo() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the TRACE-Graph demo market.")
    parser.add_argument(
        "--no-ring", action="store_true", help="leave the ring out; POST /admin/ring adds it later"
    )
    arguments = parser.parse_args()
    sys.exit(asyncio.run(seed_and_report(with_ring=not arguments.no_ring)))
