"""Execution guardrails: CPU-bound timeouts, process isolation, and input constraints."""

import asyncio
import multiprocessing as mp
import sys
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_INPUT_LENGTH = 4096


class ComputationTimeoutError(TimeoutError):
    """Raised when calculation exceeds the maximum allowed time budget."""


class InputExceededError(ValueError):
    """Raised when mathematical input exceeds the maximum length."""


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
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Execute a function inside a dedicated process with strict hard timeout.

    If the function does not complete within timeout_seconds, the process
    is terminated immediately to prevent runaway CPU or memory locks.
    """
    if kwargs is None:
        kwargs = {}

    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker_target, args=(q, func, args, kwargs))

    proc.start()
    proc.join(timeout=timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=0.5)
        if proc.is_alive():
            proc.kill()
            proc.join()
        raise ComputationTimeoutError(
            f"Computation timed out after {timeout_seconds:.1f} seconds. "
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
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Async wrapper around run_with_timeout to avoid blocking the event loop."""
    return await asyncio.to_thread(run_with_timeout, func, args, kwargs, timeout_seconds)


def validate_input_length(text: str, max_length: int = MAX_INPUT_LENGTH) -> None:
    """Ensure the input doesn't exceed reasonable complexity bounds."""
    if len(text) > max_length:
        raise InputExceededError(
            f"Input length {len(text)} characters exceeds maximum allowed {max_length} characters."
        )
