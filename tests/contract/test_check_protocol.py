"""Contract tests: every registered check satisfies the Check protocol.

The protocol analogue of GoldMind's connector-parity tests — any check, present
or future, must conform to the same shape so the runner and CLI stay agnostic.
"""

from __future__ import annotations

import pytest

from forecastguard.checks import Check, CheckContext, default_checks
from forecastguard.checks.runtime_leak import RuntimeLeakageCheck
from forecastguard.models.report import CheckResult, CheckStatus

pytestmark = pytest.mark.contract


def test_default_checks_satisfy_protocol() -> None:
    checks = default_checks()
    assert len(checks) == 3
    for check in checks:
        assert isinstance(check, Check)
        assert isinstance(check.check_id, str) and check.check_id
        assert isinstance(check.name, str) and check.name


def test_check_ids_are_unique() -> None:
    ids = [check.check_id for check in default_checks()]
    assert len(ids) == len(set(ids))


def test_each_check_returns_a_checkresult(check_context: CheckContext) -> None:
    for check in default_checks():
        result = check.run(check_context)
        assert isinstance(result, CheckResult)
        assert result.check_id == check.check_id


def test_runtime_leak_skips_loudly_without_feature_fn(
    check_context: CheckContext,
) -> None:
    result = RuntimeLeakageCheck().run(check_context)  # context has no feature_fn
    assert result.status is CheckStatus.SKIPPED
    assert "feature_fn" in (result.detail or "")
