from pathlib import Path

from tracegraph.eval.checkpoint import append_finished, checkpoint_path, load_finished
from tracegraph.eval.outcomes import SeedResult


def test_a_restarted_run_gets_back_only_markets_from_the_same_settings(tmp_path: Path) -> None:
    path = checkpoint_path(str(tmp_path))
    played = SeedResult("guarded", "strat", 1000, fraud_sats=12, round_ms=[1.5], fraud_by_round=[3])
    append_finished(path, "hash-now", played)
    append_finished(path, "hash-before", SeedResult("guarded", "strat", 1001))
    assert load_finished(path, "hash-now") == {("guarded", "strat", 1000): played}


def test_no_checkpoint_means_nothing_played(tmp_path: Path) -> None:
    assert load_finished(checkpoint_path(str(tmp_path)), "hash-now") == {}
