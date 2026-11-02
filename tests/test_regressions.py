"""Regression coverage for safe parsing, numeric fidelity, and JSON tool results."""

from decimal import Decimal
from fractions import Fraction
import json

import pytest
import sympy as sp

from math_tools import engine
from math_tools.server import server


@pytest.mark.parametrize(
    ("expression", "exact"),
    [
        ("sin(pi/2) + cos(0)", "2"),
        ("sqrt(256) + 2^5", "48"),
        ("log(1000, 10)", "3"),
        ("log10(100) + log2(8)", "5"),
        ("abs(-3) + floor(5/2) + ceil(5/2)", "8"),
        ("min(3, 2) + max(1, 5)", "7"),
        ("round(1.23456, 2)", "123/100"),
        ("7//2", "3"),
        ("0.1 + 0.2", "3/10"),
        ("1.234567890123456789 - 1.234567890123456788", "1/1000000000000000000"),
        ("1_000.25 - 1000", "1/4"),
    ],
)
def test_safe_plain_arithmetic_and_exact_decimals(expression, exact):
    result = engine._evaluate_expression_worker(expression, 30)
    assert result["status"] == "success"
    assert result["exact_text"] == exact
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_plain_expression_parser_supports_modulo_directly():
    parsed = engine._parse_plain_expression("7//2 + 7%2")
    assert str(parsed) == "4"


@pytest.mark.parametrize(
    "expression",
    [
        "'1+2'", "b'123'", "True", "None", "1j",
        "[1, 2]", "(1, 2)", "{'x': 1}", "{1, 2}",
        "(x for x in [1])", "lambda: 1", "x.y", "x[0]",
        "__private", "_private", "x__class__", "x# ignored suffix",
        "unknown(1)", "Integer(1)", "Symbol('x')", "Rational(1, 2)",
        "__import__('forbidden_module')", "getattr(x, 'y')",
        "sin(x=1)", "sin(*(1,))", "(lambda: 1)()",
    ],
)
def test_forbidden_plain_syntax_is_not_executed(expression):
    # Inputs are inert: even a regression must not execute an OS payload.
    with pytest.raises(ValueError):
        engine._evaluate_expression_worker(expression, 10)
    with pytest.raises(ValueError):
        engine._evaluate_latex_worker(expression, 10)
    with pytest.raises(ValueError):
        engine._solve_equation_worker(f"{expression} = 0", None)


@pytest.mark.parametrize("text", [r"\frac{1}{2} +", r"\sqrt{4} +", "1 +", "x=1=2"])
def test_latex_must_consume_the_entire_input(text):
    with pytest.raises(ValueError):
        engine._evaluate_latex_worker(text, 10)


def test_parser_never_uses_nonstrict_latex_fallback(monkeypatch):
    calls = []

    def reject(text, **options):
        calls.append(options)
        raise ValueError("unsupported input")

    monkeypatch.setattr(engine, "parse_latex", reject)
    with pytest.raises(ValueError):
        engine._parse_latex_expression(r"\unsupported{1}")
    assert {call["backend"] for call in calls} == {"antlr", "lark"}
    assert all(call["strict"] is True for call in calls)


@pytest.mark.parametrize(
    "variables",
    [
        [], {"x": True}, {"x": None}, {"x": [1]}, {"x": {"a": 1}},
        {"x": float("nan")}, {"x": float("inf")}, {"x": -float("inf")},
        {"x": Decimal("NaN")}, {"x": complex(1, 2)},
        {"x": sp.oo}, {"x": sp.Symbol("y")},
        {"x": "nan"}, {"x": "inf"}, {"x": "1/0"}, {"x": "1/2/3"},
        {"x": "sqrt(2)"}, {"x": "2+2"}, {"x": "Integer(7)"},
        {"x": "__import__('forbidden_module')"},
        {"x": "1e1001"}, {"x": "1" * 257}, {"x": 2**4097},
        {"sin": 1}, {"sqrt": 2}, {"Integer": 3}, {"pi": 3},
        {"__private": 1}, {"_private": 1}, {"a__b": 1}, {"a.b": 1},
        {"1x": 1}, {"a" * 65: 1}, {1: 2}, {"λ": 1},
        {f"x{index}": index for index in range(65)},
    ],
)
def test_variable_mappings_rejected_before_computation(monkeypatch, variables):
    def must_not_run(*args, **kwargs):
        pytest.fail("Invalid variable mappings reached process execution.")

    monkeypatch.setattr(engine, "run_with_timeout", must_not_run)
    with pytest.raises(ValueError):
        engine.evaluate_expression("999999^999999", variables=variables)
    with pytest.raises(ValueError):
        engine.evaluate_latex(r"\int_0^1 x dx", variables=variables)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2, "2"), (0.5, "0.500000000000000"),
        ("0.125", "1/8"), ("1.25e-3", "1/800"),
        ("-3 / 4", "-3/4"), ("1.5/0.5", "3"),
        (Decimal("0.125"), "1/8"), (Fraction(1, 3), "1/3"),
        (sp.Rational(2, 3), "2/3"),
    ],
)
def test_finite_numeric_variable_values(value, expected):
    result = engine._evaluate_expression_worker("x", 20, variables={"x": value})
    assert result["exact_text"] == expected
    assert result["free_variables"] == []
    assert result["numeric_approximation"] is not None


def test_public_wrapper_preserves_numeric_string_substitutions():
    result = engine.evaluate_expression("x + y", variables={"x": "1/3", "y": "0.125"})
    assert result["exact_text"] == "11/24"
    assert result["numeric_approximation"] == 0.4583333333


@pytest.mark.parametrize("precision", [0, -1, 101, 1000000, True, 1.5, "20", None])
def test_precision_is_bounded_before_computation(monkeypatch, precision):
    def must_not_run(*args, **kwargs):
        pytest.fail("Invalid precision reached process execution.")

    monkeypatch.setattr(engine, "run_with_timeout", must_not_run)
    with pytest.raises(ValueError):
        engine.evaluate_expression("1/3", precision=precision)
    with pytest.raises(ValueError):
        engine.evaluate_latex(r"\frac{1}{3}", precision=precision)


@pytest.mark.parametrize("expression", ["1e-34", "-1e-34", "6.67430e-11", "8.8541878128e-12"])
def test_tiny_floats_are_not_zeroed_or_distorted(expression):
    result = engine._evaluate_expression_worker(expression, 10)
    assert result["numeric_approximation"] == pytest.approx(float(Decimal(expression)), rel=1e-9, abs=0)
    assert Decimal(result["numeric_decimal"]) != 0


def test_physics_tiny_constant_substitution_and_decimal_output():
    result = engine.evaluate_expression("h", precision=30, use_physics=True)
    assert result["numeric_approximation"] == pytest.approx(6.62607015e-34, rel=1e-10, abs=0)
    assert Decimal(result["numeric_decimal"]) == Decimal("6.62607015e-34")


def test_decimal_output_is_high_precision_not_a_stringified_machine_float():
    result = engine.evaluate_expression("1/3", precision=50)
    assert result["numeric_decimal"] == "0." + "3" * 50
    assert result["numeric_approximation"] == float(1 / 3)
    ordinary = engine._evaluate_latex_worker(r"\frac{3491 \times 18}{7}", 10)
    assert ordinary["numeric_approximation"] == 8976.8571428571


@pytest.mark.parametrize("text", ["1e-400", "1e400"])
def test_decimal_string_survives_machine_float_range_limits(text):
    result = engine._evaluate_expression_worker(text, 30)
    assert result["numeric_approximation"] is None
    assert Decimal(result["numeric_decimal"]) == Decimal(text)
    json.dumps(result, allow_nan=False)


def test_zero_and_nonreal_numeric_results():
    assert engine._safe_float(sp.Float(0)) == 0.0
    result = engine._evaluate_expression_worker("sqrt(-1)", 20)
    assert result["numeric_approximation"] is None
    assert result["numeric_decimal"] is None
    for text in ("1/0", "0/0"):
        result = engine._evaluate_expression_worker(text, 20)
        assert result["numeric_approximation"] is None
        assert result["numeric_decimal"] is None
        json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("equation", "identity", "contradiction"),
    [("2+2=4", True, False), ("2+2=5", False, True),
     ("x=x", True, False), ("x=x+1", False, True)],
)
def test_identity_and_contradiction_equations_at_public_boundary(equation, identity, contradiction):
    result = engine.solve_equation(equation)
    assert result["status"] == "success"
    assert result["is_identity"] is identity
    assert result["is_contradiction"] is contradiction
    assert result["solutions_count"] == 0
    assert result["solutions_text"] == []
    assert result["solutions_numeric"] == []
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_plain_equation_sides_use_exact_decimal_parser():
    result = engine.solve_equation("0.1*x + 0.2 = 0.5")
    assert result["solutions_text"] == ["3"]
    assert result["is_identity"] is False
    assert result["is_contradiction"] is False


@pytest.mark.parametrize("variable", ["sin", "Integer", "__private", "x.y", "x" * 65])
def test_invalid_solve_variable_is_rejected(variable):
    with pytest.raises(ValueError):
        engine.solve_equation("x=1", variable=variable)


@pytest.mark.parametrize(("text", "exact"), [("5!", "120"), ("(3+2)!", "120"), ("2*3!", "12"), ("factorial(5)", "120")])
def test_factorial_not_lost_to_punctuation(text, exact):
    for worker in (engine._evaluate_expression_worker, engine._evaluate_latex_worker):
        assert worker(text, 10)["exact_text"] == exact


def test_derivative_substitution_happens_after_differentiation():
    result = engine.evaluate_latex(r"\frac{d}{dx} x^3", variables={"x": "1/2"})
    assert result["exact_text"] == "3/4"
    assert result["numeric_approximation"] == 0.75


def test_matrix_exact_cells_and_substitutions_at_public_boundary():
    result = engine.evaluate_latex(
        r"\begin{pmatrix} x & \frac{1}{3} \\ \sqrt{2} & y \end{pmatrix}",
        variables={"x": "1/2", "y": 4},
    )
    assert result["type"] == "matrix"
    assert result["shape"] == [2, 2]
    assert result["matrix_data"] == [["1/2", "1/3"], ["sqrt(2)", 4]]
    assert result["trace"] == 4.5
    assert result["determinant"] == pytest.approx(2 - 2**0.5 / 3)
    assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.anyio
async def test_matrix_output_is_serializable_at_server_boundary():
    response = await server.call_tool(
        "evaluate_latex",
        {"latex": r"\begin{pmatrix} 1 & x \\ 3 & 4 \end{pmatrix}", "variables": {"x": "1/2"}},
    )
    assert not response.is_error
    result = json.loads(response.content[0].text)
    assert result["status"] == "success"
    assert result["matrix_data"] == [[1, "1/2"], [3, 4]]
    assert result["determinant"] == 2.5


def test_windows_hard_numeric_integral_skips_symbolic_integration(monkeypatch):
    variable = sp.Symbol("x")
    integral = sp.Integral((variable**2 - 2) / ((variable**2 + 2) * sp.sqrt(variable**4 + 4)), (variable, 0, 1))

    def must_not_integrate(*args, **kwargs):
        pytest.fail("Closed difficult integral entered the unbounded symbolic integrator.")

    monkeypatch.setattr(engine.sys, "platform", "win32")
    monkeypatch.setattr(sp.Integral, "doit", must_not_integrate)
    monkeypatch.setattr(sp, "integrate", must_not_integrate)
    assert engine._evaluate_scalar(integral, {}, 5.0) == integral


def test_difficult_numeric_integral_retains_exact_form_and_numeric_result():
    result = engine.evaluate_latex(
        r"\int_{0}^{1} \frac{x^2-2}{(x^2+2) \sqrt{x^4+4}} \, dx",
        timeout_seconds=5.0,
    )
    assert result["status"] == "success"
    assert "Integral(" in result["exact_text"]
    assert result["is_number"] is True
    assert result["numeric_approximation"] == pytest.approx(-0.3648638281, abs=1e-9)
    assert Decimal(result["numeric_decimal"]) == pytest.approx(Decimal("-0.3648638281"), abs=Decimal("1e-9"))
