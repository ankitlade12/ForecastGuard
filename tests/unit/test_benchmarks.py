"""The public mutation and scale benchmarks remain executable."""

from __future__ import annotations

import pytest
from benchmarks.mutation_benchmark import run_mutations
from benchmarks.scale_benchmark import run_scale

pytestmark = pytest.mark.unit


def test_mutation_corpus_detects_all_seeded_leaks_and_passes_controls() -> None:
    result = run_mutations()
    assert result["all_correct"] is True
    assert result["correct"] == result["total"]


def test_scale_benchmark_returns_machine_readable_evidence() -> None:
    result = run_scale(series=10, periods=40, horizon=7)
    assert result["status"] == "pass"
    assert result["rows"] == 400
    assert isinstance(result["polars_recommended"], bool)
