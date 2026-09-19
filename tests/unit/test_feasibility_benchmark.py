"""Benchmark scoring must not confuse blocking, detection, and abstention."""

from __future__ import annotations

import pytest
from benchmarks.feasibility_benchmark import Observation, score_observations

from forecastguard.models.report import CheckResult, Severity, Violation

pytestmark = pytest.mark.unit


def test_abstentions_do_not_inflate_detection_or_clean_acceptance() -> None:
    skipped = CheckResult.skipped("runtime_leakage", "Runtime", "missing callable")
    error = CheckResult.errored("runtime_leakage", "Runtime", "crashed")
    rows = [
        Observation(case="leak_skip", kind="leak", results=[skipped]),
        Observation(case="leak_error", kind="leak", results=[error]),
        Observation(case="clean_skip", kind="clean", results=[skipped]),
    ]
    score = score_observations(rows)
    assert score.leak_detections == 0
    assert score.leak_misses == 2
    assert score.abstentions == 3
    assert score.clean_passes == 0
    assert score.clean_false_alarms == 0
    assert score.leak_detection_rate == 0


def test_blind_spots_remain_visible_and_strict_blocking_is_separate() -> None:
    passed = CheckResult.passed("runtime_leakage", "Runtime", "no sensitivity")
    failed = CheckResult.failed(
        "runtime_leakage",
        "Runtime",
        "sensitivity",
        [Violation(code="FG-LEAK-001", severity=Severity.CRITICAL, message="changed")],
    )
    skipped = CheckResult.skipped("runtime_leakage", "Runtime", "missing callable")
    score = score_observations(
        [
            Observation(case="detected", kind="leak", results=[failed]),
            Observation(case="clean", kind="clean", results=[passed]),
            Observation(case="cached", kind="boundary", results=[passed]),
            Observation(case="missing", kind="guard", results=[skipped]),
        ]
    )
    assert score.leak_detection_rate == 1
    assert score.boundary_misses == 1
    assert score.all_leak_detection_rate == 0.5
    assert score.guard_strict_blocks == 1
    assert score.clean_passes == 1
    assert score.abstentions == 1


def test_empty_denominators_are_not_perfect_scores() -> None:
    score = score_observations([])
    assert score.leak_detection_rate is None
    assert score.all_leak_detection_rate is None
    assert score.clean_false_alarm_rate is None
