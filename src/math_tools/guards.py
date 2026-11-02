"""Execution guardrails: CPU-bound timeouts, process isolation, and input constraints."""

import asyncio
import math
import multiprocessing as mp
import queue
import sys
import threading
import time
from multiprocessing.connection import Connection
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
MIN_TIMEOUT_SECONDS = 0.1
MAX_INPUT_LENGTH = 4096

_CLEANUP_TIMEOUT_SECONDS = 0.5
_MP_CONTEXT: Optional[Any] = None


class ComputationTimeoutError(TimeoutError):
    """Raised when calculation exceeds the maximum allowed time budget."""


class InputExceededError(ValueError):
    """Raised when mathematical input exceeds the maximum length."""


def clamp_timeout(timeout: Optional[float]) -> float:
    """Clamp finite budgets to the allowed range; invalid values use the default."""
    if timeout is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        val = float(timeout)
    except (ValueError, TypeError, OverflowError):
        return DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(val):
        return DEFAULT_TIMEOUT_SECONDS
    return max(MIN_TIMEOUT_SECONDS, min(val, MAX_TIMEOUT_SECONDS))


def get_mp_context() -> Any:
    """Retrieve optimal multiprocessing context with forkserver preloading on Linux."""
    global _MP_CONTEXT
    if _MP_CONTEXT is not None:
        return _MP_CONTEXT

    if sys.platform != "win32":
        try:
            ctx = mp.get_context("forkserver")
            ctx.set_forkserver_preload(["sympy", "math_tools.guards", "math_tools.engine"])
            _MP_CONTEXT = ctx
            return _MP_CONTEXT
        except Exception:
            pass

    _MP_CONTEXT = mp.get_context("spawn")
    return _MP_CONTEXT


def _worker_target(
    result_connection: Connection,
    func: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> None:
    """Execute and send a single response without a background queue feeder."""
    try:
        try:
            result = func(*args, **kwargs)
            result_connection.send(("ok", result))
        except Exception as exc:
            result_connection.send(("error", exc))
    finally:
        result_connection.close()


def _receive_worker_result(connection: Connection, responses: queue.Queue) -> None:
    """Drain the pipe while the worker runs, including responses larger than its buffer."""
    try:
        responses.put((True, connection.recv()))
    except Exception as exc:
        responses.put((False, exc))


def _cleanup_process(proc: Any) -> None:
    """Reap a worker with bounded waits, including after a failed start.

    Process handles are released by standard finalizers rather than calling
    proc.close() explicitly, preventing race conditions with multiprocessing's
    internal child polling on Windows.
    """
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=_CLEANUP_TIMEOUT_SECONDS)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=_CLEANUP_TIMEOUT_SECONDS)


def run_with_timeout(
    func: Callable[..., Any],
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Execute a function in a dedicated process with a bounded response wait.

    The budget starts after Process.start() returns (starting is not interruptible)
    and includes worker initialization, execution, response transfer, and normal
    worker shutdown. Timeout cleanup adds at most three 0.5-second waits for
    terminate, kill, and the response reader. Isolation is not an OS sandbox and
    does not impose a memory quota.
    """
    if kwargs is None:
        kwargs = {}

    timeout = clamp_timeout(timeout_seconds)
    ctx = get_mp_context()
    # A one-way pipe has no feeder to join and reports EOF when a worker exits
    # without a response. The parent must close its copy of the writing end.
    result_connection, worker_connection = ctx.Pipe(duplex=False)
    proc = None
    reader = None
    try:
        proc = ctx.Process(
            target=_worker_target, args=(worker_connection, func, args, kwargs)
        )
        proc.start()
        deadline = time.monotonic() + timeout
        worker_connection.close()

        responses: queue.Queue = queue.Queue()
        # Even a timed Queue.get()/Connection.poll() can block on a partial
        # message. Keep receiving off this thread so the deadline stays bounded.
        reader = threading.Thread(
            target=_receive_worker_result,
            args=(result_connection, responses),
            daemon=True,
        )
        reader.start()
        try:
            received, response = responses.get(
                timeout=max(0.0, deadline - time.monotonic())
            )
        except queue.Empty:
            raise ComputationTimeoutError(
                f"Computation timed out after {timeout:.1f} seconds. "
                "Expression may be excessively complex or non-terminating."
            ) from None

        # Drain before joining: a large response can otherwise prevent exit.
        proc.join(timeout=max(0.0, deadline - time.monotonic()))
        if proc.is_alive():
            raise ComputationTimeoutError(
                f"Computation timed out after {timeout:.1f} seconds. "
                "Expression may be excessively complex or non-terminating."
            )

        if received:
            status, payload = response
            if status == "ok":
                return payload
            # Re-raise the original exception object.
            raise payload

        if not isinstance(response, (EOFError, OSError)):
            raise response
        if proc.exitcode != 0:
            raise RuntimeError(f"Process crashed with exit code {proc.exitcode}")
        raise RuntimeError("Worker process completed without returning a result.")
    finally:
        try:
            if proc is not None:
                _cleanup_process(proc)
        finally:
            worker_connection.close()
            result_connection.close()
            if reader is not None and reader.ident is not None:
                reader.join(timeout=_CLEANUP_TIMEOUT_SECONDS)


async def run_with_timeout_async(
    func: Callable[..., Any],
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Async wrapper around run_with_timeout to avoid blocking the event loop."""
    timeout = clamp_timeout(timeout_seconds)
    return await asyncio.to_thread(run_with_timeout, func, args, kwargs, timeout)


def validate_input_length(text: str, max_length: int = MAX_INPUT_LENGTH) -> None:
    """Ensure the input doesn't exceed reasonable complexity bounds."""
    if len(text) > max_length:
        raise InputExceededError(
            f"Input length {len(text)} characters exceeds maximum allowed {max_length} characters."
        )
