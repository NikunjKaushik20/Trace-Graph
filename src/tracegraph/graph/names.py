from typing import Literal

View = Literal["together", "alone"]


# Name of the graph a buyer reads and writes in the given view
def graph_for_buyer(shared_graph: str, buyer_id: str, view: View) -> str:
    if view == "alone":
        return private_graph(shared_graph, buyer_id)
    return shared_graph


# Name of one buyer's private graph, used in the Alone view
def private_graph(shared_graph: str, buyer_id: str) -> str:
    return f"{shared_graph}:private:{buyer_id}"


# Name of a scoreboard graph for one lane and seed, and optionally one buyer
def eval_graph(lane: str, seed: int, buyer_id: str | None = None) -> str:
    base = f"eval:{lane}:{seed}"
    return f"{base}:{buyer_id}" if buyer_id else base
