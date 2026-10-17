"""Execution guardrails: CPU-bound timeouts, process isolation, and input constraints."""

import asyncio
import multiprocessing as mp
import sys
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
MIN_TIMEOUT_SECONDS = 0.1
MAX_INPUT_LENGTH = 4096

_MP_CONTEXT: Optional[Any] = None


class ComputationTimeoutError(TimeoutError):
    """Raised when calculation exceeds the maximum allowed time budget."""


class InputExceededError(ValueError):
    """Raised when mathematical input exceeds the maximum length."""


def clamp_timeout(timeout: Optional[float]) -> float:
    """Validate and clamp timeout budget between MIN_TIMEOUT_SECONDS and MAX_TIMEOUT_SECONDS."""
    if timeout is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        val = float(timeout)
        return max(MIN_TIMEOUT_SECONDS, min(val, MAX_TIMEOUT_SECONDS))
    except (ValueError, TypeError):
        return DEFAULT_TIMEOUT_SECONDS


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
    q: mp.Queue,
    func: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> None:
    """Target function executed in an isolated worker process."""
    try:
        result = func(*args, **kwargs)
        q.put(("ok", result))
    except Exception as exc:
        q.put(("error", exc))


def run_with_timeout(
    func: Callable[..., Any],
    args: Tuple[Any, ...] = (),
    kwargs: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Execute a function inside a dedicated process with strict hard timeout.

    If the function does not complete within timeout_seconds, the process
    is terminated immediately to prevent runaway CPU or memory locks.
    """
    if kwargs is None:
        kwargs = {}

    timeout = clamp_timeout(timeout_seconds)
    ctx = get_mp_context()
    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker_target, args=(q, func, args, kwargs))

    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=0.5)
        if proc.is_alive():
            proc.kill()
            proc.join()
        raise ComputationTimeoutError(
            f"Computation timed out after {timeout:.1f} seconds. "
            "Expression may be excessively complex or non-terminating."
        )

    if not q.empty():
        status, payload = q.get()
        if status == "ok":
            return payload
        # Re-raise the original exception object
        raise payload

    if proc.exitcode != 0:
        raise RuntimeError(f"Process crashed with exit code {proc.exitcode}")

    raise RuntimeError("Worker process completed without returning a result.")


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
