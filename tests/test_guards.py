"""Unit tests for execution guardrails and timeouts."""

import time
import pytest
from math_tools.guards import (
    ComputationTimeoutError,
    InputExceededError,
    run_with_timeout,
    validate_input_length,
)


def _fast_add(a: int, b: int) -> int:
    return a + b


def _slow_hang() -> None:
    time.sleep(3.0)


def test_run_with_timeout_success():
    result = run_with_timeout(_fast_add, args=(10, 20), timeout_seconds=1.0)
    assert result == 30


def test_run_with_timeout_trigger():
    with pytest.raises(ComputationTimeoutError):
        run_with_timeout(_slow_hang, timeout_seconds=0.3)


def test_validate_input_length():
    validate_input_length("x = 10", max_length=50)
    with pytest.raises(InputExceededError):
        validate_input_length("x" * 100, max_length=50)
