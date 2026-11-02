"""Unit tests for execution guardrails and timeouts."""

import multiprocessing as mp
import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import math_tools.guards as guards
from math_tools.guards import (
    ComputationTimeoutError,
    InputExceededError,
    clamp_timeout,
    run_with_timeout,
    validate_input_length,
)


# Keep worker functions at module scope so they can be imported with spawn.
def _fast_add(a: int, b: int) -> int:
    return a + b


def _large_result() -> bytes:
    return bytes(range(256)) * 4096


def _raise_value_error() -> None:
    raise ValueError("worker calculation failed")


def _hard_crash() -> None:
    os._exit(7)


def _exit_without_result() -> None:
    os._exit(0)


def _slow_hang() -> None:
    time.sleep(10.0)


def test_run_with_timeout_success():
    result = run_with_timeout(_fast_add, args=(10, 20), timeout_seconds=10.0)
    assert result == 30


def test_run_with_timeout_large_result():
    # Larger than the IPC buffer: joining before reading would deadlock.
    result = run_with_timeout(_large_result, timeout_seconds=10.0)
    assert len(result) == 1024 * 1024
    assert result == _large_result()


def test_run_with_timeout_propagates_worker_exception():
    with pytest.raises(ValueError, match="^worker calculation failed$"):
        run_with_timeout(_raise_value_error, timeout_seconds=10.0)


def test_run_with_timeout_reports_hard_crash():
    with pytest.raises(RuntimeError, match="^Process crashed with exit code 7$"):
        run_with_timeout(_hard_crash, timeout_seconds=10.0)


def test_run_with_timeout_reports_missing_result():
    with pytest.raises(
        RuntimeError, match="^Worker process completed without returning a result\\.$"
    ):
        run_with_timeout(_exit_without_result, timeout_seconds=10.0)


def test_run_with_timeout_trigger_and_next_request_success():
    with pytest.raises(ComputationTimeoutError, match="timed out after 0.3 seconds"):
        run_with_timeout(_slow_hang, timeout_seconds=0.3)
    assert run_with_timeout(_fast_add, args=(2, 3), timeout_seconds=10.0) == 5


def test_run_with_timeout_cleans_resources_after_failed_start(monkeypatch):
    result_connection = Mock()
    worker_connection = Mock()
    proc = Mock()
    proc.start.side_effect = OSError("worker failed to start")
    proc.is_alive.return_value = False
    context = SimpleNamespace(
        Pipe=Mock(return_value=(result_connection, worker_connection)),
        Process=Mock(return_value=proc),
    )
    monkeypatch.setattr(guards, "get_mp_context", lambda: context)

    with pytest.raises(OSError, match="^worker failed to start$"):
        run_with_timeout(_fast_add, args=(1, 2))

    proc.close.assert_not_called()
    proc.join.assert_not_called()
    proc.terminate.assert_not_called()
    result_connection.close.assert_called_once_with()
    worker_connection.close.assert_called_once_with()


def test_run_with_timeout_cleans_connections_after_process_constructor_failure(monkeypatch):
    result_connection = Mock()
    worker_connection = Mock()
    context = SimpleNamespace(
        Pipe=Mock(return_value=(result_connection, worker_connection)),
        Process=Mock(side_effect=OSError("worker could not be created")),
    )
    monkeypatch.setattr(guards, "get_mp_context", lambda: context)

    with pytest.raises(OSError, match="^worker could not be created$"):
        run_with_timeout(_fast_add, args=(1, 2))

    result_connection.close.assert_called_once_with()
    worker_connection.close.assert_called_once_with()


def test_run_with_timeout_can_bound_a_stalled_response_reader(monkeypatch):
    # A pipe may become readable before the full message is available. A blocked
    # recv must not prevent the caller from enforcing the response deadline.
    release_reader = threading.Event()
    finished_reader = threading.Event()

    def stalled_receive():
        try:
            release_reader.wait()
            raise EOFError
        finally:
            finished_reader.set()

    result_connection = Mock()
    result_connection.recv.side_effect = stalled_receive
    result_connection.close.side_effect = release_reader.set
    worker_connection = Mock()
    proc = Mock()
    proc.is_alive.side_effect = [True, False, False]
    context = SimpleNamespace(
        Pipe=Mock(return_value=(result_connection, worker_connection)),
        Process=Mock(return_value=proc),
    )
    monkeypatch.setattr(guards, "get_mp_context", lambda: context)

    try:
        with pytest.raises(ComputationTimeoutError):
            run_with_timeout(_fast_add, args=(1, 2), timeout_seconds=0.1)
    finally:
        release_reader.set()

    assert finished_reader.wait(timeout=1.0)
    proc.terminate.assert_called_once_with()
    proc.close.assert_not_called()
    result_connection.close.assert_called_once_with()


def test_process_cleanup_uses_bounded_terminate_and_kill_joins():
    proc = Mock()
    # Still alive after terminate, then stopped after kill.
    proc.is_alive.side_effect = [True, True, False]

    guards._cleanup_process(proc)

    proc.terminate.assert_called_once_with()
    proc.kill.assert_called_once_with()
    assert proc.join.call_count == 2
    for call in proc.join.call_args_list:
        assert 0 < call.kwargs["timeout"] <= 0.5
    proc.close.assert_not_called()


def test_process_cleanup_does_not_close_a_still_running_process():
    proc = Mock()
    proc.is_alive.return_value = True

    guards._cleanup_process(proc)

    assert proc.join.call_count == 2
    for call in proc.join.call_args_list:
        assert 0 < call.kwargs["timeout"] <= 0.5
    proc.close.assert_not_called()


def test_get_mp_context_selects_spawn_on_windows(monkeypatch):
    spawn_context = mp.get_context("spawn")
    get_context = Mock(return_value=spawn_context)
    monkeypatch.setattr(guards, "_MP_CONTEXT", None)
    monkeypatch.setattr(guards.sys, "platform", "win32")
    monkeypatch.setattr(guards.mp, "get_context", get_context)

    assert guards.get_mp_context() is spawn_context
    assert guards.get_mp_context() is spawn_context
    get_context.assert_called_once_with("spawn")


def test_run_with_timeout_using_spawn(monkeypatch):
    monkeypatch.setattr(guards, "_MP_CONTEXT", mp.get_context("spawn"))
    assert run_with_timeout(_fast_add, args=(3, 4), timeout_seconds=10.0) == 7


@pytest.mark.parametrize(
    "timeout", [None, "invalid", object(), float("nan"), float("inf"), float("-inf"), 10**400]
)
def test_clamp_timeout_invalid_values_use_default(timeout):
    assert clamp_timeout(timeout) == guards.DEFAULT_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("timeout", "expected"),
    [(-1, 0.1), (0, 0.1), (0.2, 0.2), (100, 30.0), ("2.5", 2.5)],
)
def test_clamp_timeout_valid_values(timeout, expected):
    assert clamp_timeout(timeout) == expected


def test_validate_input_length():
    validate_input_length("x = 10", max_length=50)
    with pytest.raises(InputExceededError):
        validate_input_length("x" * 100, max_length=50)
