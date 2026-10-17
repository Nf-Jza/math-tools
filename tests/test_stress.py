"""Stress, security, and edge-case testing suite for math-tools engine."""

from concurrent.futures import ThreadPoolExecutor
import pytest

from math_tools.engine import evaluate_expression, evaluate_latex, solve_equation
from math_tools.guards import ComputationTimeoutError, InputExceededError


# ---------------------------------------------------------
# 1. Security & Sandbox Escape Tests
# ---------------------------------------------------------
def test_security_rejection_rce():
    malicious_payloads = [
        '__import__("os").system("echo pwned")',
        'open("/etc/passwd").read()',
        "().__class__.__base__.__subclasses__()",
        "getattr(math, 'sqrt')(16)",
        "exec('a = 10')",
        "eval('5 + 5')",
        "lambda x: x + 1",
    ]
    for payload in malicious_payloads:
        with pytest.raises(Exception):
            evaluate_expression(payload)


# ---------------------------------------------------------
# 2. Timeout & ReDoS / CPU Burner Tests
# ---------------------------------------------------------
def test_timeout_catastrophic_power():
    with pytest.raises(ComputationTimeoutError):
        evaluate_expression("999999^999999", timeout=1.0)


def test_timeout_huge_combinatorial_expansion():
    with pytest.raises(ComputationTimeoutError):
        evaluate_expression("(x + y + z + w + v + u)**25", timeout=1.0)


# ---------------------------------------------------------
# 3. Advanced Calculus, Matrices, and Limits
# ---------------------------------------------------------
def test_nested_fractions():
    res = evaluate_latex(r"\frac{\frac{1}{2}}{\frac{3}{4}}")
    assert res["status"] == "success"
    assert res["exact_text"] == "2/3"
    assert res["numeric_approximation"] == 0.6666666667


def test_matrix_parsing_and_determinant():
    res = evaluate_latex(r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}")
    assert res["status"] == "success"
    assert res["type"] == "matrix"
    assert res["shape"] == [2, 2]
    assert res["matrix_data"] == [[1, 2], [3, 4]]
    assert res["determinant"] == -2.0
    assert res["trace"] == 5.0


def test_finite_summation():
    res = evaluate_latex(r"\sum_{k=1}^{100} k")
    assert res["status"] == "success"
    assert res["exact_text"] == "5050"
    assert res["numeric_approximation"] == 5050.0


def test_infinite_summation():
    # Basel problem: \sum_{n=1}^\infty \frac{1}{n^2} = \pi^2 / 6
    res = evaluate_latex(r"\sum_{n=1}^{\infty} \frac{1}{n^2}")
    assert res["status"] == "success"
    assert "pi" in res["exact_text"].lower()
    assert abs(res["numeric_approximation"] - 1.6449340668) < 1e-6


def test_limit_to_infinity():
    res = evaluate_latex(r"\lim_{x \to \infty} \left(1 + \frac{1}{x}\right)^x")
    assert res["status"] == "success"
    assert res["exact_text"] == "E"
    assert abs(res["numeric_approximation"] - 2.7182818285) < 1e-6


def test_gaussian_integral():
    # \int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
    res = evaluate_latex(r"\int_{-\infty}^{\infty} e^{-x^2} dx")
    assert res["status"] == "success"
    assert "sqrt(pi)" in res["exact_text"].lower()
    assert abs(res["numeric_approximation"] - 1.7724538509) < 1e-6


# ---------------------------------------------------------
# 4. Fuzzing, Malformed Syntax, & Length Boundaries
# ---------------------------------------------------------
def test_input_length_boundary():
    huge_input = "1 + " * 3000 + "1"
    with pytest.raises(InputExceededError):
        evaluate_expression(huge_input)


def test_malformed_unclosed_braces():
    with pytest.raises(Exception):
        evaluate_latex(r"\frac{1}{2")


def test_empty_string_rejection():
    with pytest.raises(Exception):
        evaluate_latex("")

    with pytest.raises(Exception):
        evaluate_expression("")


# ---------------------------------------------------------
# 5. Concurrent High-Throughput Load
# ---------------------------------------------------------
def test_concurrent_throughput():
    expressions = [
        "15% of 850",
        "sqrt(256) + 2^5",
        "(453 * 12) / (7 + 3)",
        "2^10",
        "sin(pi / 2)",
        "log(1000, 10)",
    ] * 5  # 30 concurrent calculations

    def run_calc(expr: str):
        return evaluate_expression(expr)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(run_calc, expressions))

    assert len(results) == 30
    for r in results:
        assert r["status"] == "success"
        assert r["numeric_approximation"] is not None
