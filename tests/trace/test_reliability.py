import pytest

from tracegraph.trace.reliability import (
    bayesian_lcb,
    cusum_statistic,
    exclusion_reason,
    smoothed_default_rate,
    wilson_lower_bound,
)
from tracegraph.trace.settings import TraceSettings

SETTINGS = TraceSettings()


def test_cold_start_sits_near_the_pessimistic_prior() -> None:
    assert 0.0 < bayesian_lcb(0, 0, SETTINGS) < 0.25


def test_lcb_grows_with_evidence_at_the_same_success_rate() -> None:
    assert bayesian_lcb(9, 1, SETTINGS) < bayesian_lcb(90, 10, SETTINGS)


def test_lcb_drops_after_failures() -> None:
    assert bayesian_lcb(10, 5, SETTINGS) < bayesian_lcb(10, 0, SETTINGS)


def test_wilson_bound_stays_inside_zero_and_one() -> None:
    assert wilson_lower_bound(0, 0, 1.96) == 0.0
    assert 0.0 <= wilson_lower_bound(5, 5, 1.96) <= 1.0
    assert wilson_lower_bound(100, 100, 1.96) <= 1.0


def test_smoothed_default_rate_weights_recent_failures_more() -> None:
    early_failure = smoothed_default_rate([False, True, True, True], SETTINGS)
    late_failure = smoothed_default_rate([True, True, True, False], SETTINGS)
    assert late_failure > early_failure


def test_cusum_rises_on_failures_and_floors_at_zero() -> None:
    assert cusum_statistic([True] * 10, SETTINGS) == 0.0
    assert cusum_statistic([False] * 3, SETTINGS) == pytest.approx(3 * 0.625)


def test_cusum_alarm_excludes_a_provider_that_turns_bad() -> None:
    outcomes = [True] * 10 + [False] * 8
    assert exclusion_reason(outcomes, SETTINGS) == "cusum_alarm"


def test_failure_rate_above_honest_level_excludes() -> None:
    outcomes = [True, False] * 10
    assert exclusion_reason(outcomes, SETTINGS) is not None


def test_honest_record_is_not_excluded() -> None:
    outcomes = [True] * 18 + [False] * 2
    assert exclusion_reason(outcomes, SETTINGS) is None
