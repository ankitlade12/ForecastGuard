"""Best-effort AST hints that explain, but never determine, a verdict."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from typing import Literal

from forecastguard.models.hint import SourceHint


def source_hints(
    fn: Callable[..., object],
    callable_ref: str,
    component: Literal["feature", "forecast"],
) -> list[SourceHint]:
    """Find a small set of known risky constructs in a callable's source."""
    try:
        lines, start = inspect.getsourcelines(fn)
        path = inspect.getsourcefile(fn)
        tree = ast.parse(textwrap.dedent("".join(lines)))
    except (OSError, TypeError, SyntaxError):
        return []
    hints: list[SourceHint] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        rule: str | None = None
        message: str | None = None
        if node.func.attr == "shift" and _negative_shift(node):
            rule = "forward-shift"
            message = "negative shift reads a later row"
        elif node.func.attr == "rolling" and _true_keyword(node, "center"):
            rule = "centered-window"
            message = "centered rolling windows include later observations"
        elif node.func.attr == "transform" and _string_argument(node, "mean"):
            rule = "whole-series-transform"
            message = "whole-series transform may cross the validation origin"
        if rule is not None and message is not None:
            hints.append(
                SourceHint(
                    component=component,
                    callable_ref=callable_ref,
                    rule=rule,
                    message=message,
                    line=start + node.lineno - 1,
                    path=path,
                )
            )
    return hints


def _negative_shift(call: ast.Call) -> bool:
    values = list(call.args)
    values.extend(keyword.value for keyword in call.keywords if keyword.arg == "periods")
    return any(
        isinstance(value, ast.UnaryOp)
        and isinstance(value.op, ast.USub)
        and isinstance(value.operand, ast.Constant)
        and isinstance(value.operand.value, int | float)
        for value in values
    )


def _true_keyword(call: ast.Call, name: str) -> bool:
    return any(
        keyword.arg == name
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in call.keywords
    )


def _string_argument(call: ast.Call, expected: str) -> bool:
    return any(isinstance(value, ast.Constant) and value.value == expected for value in call.args)
