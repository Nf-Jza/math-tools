"""Unit tests for the core mathematical computation engine."""

import pytest
from math_tools.engine import evaluate_expression, evaluate_latex, solve_equation


def test_evaluate_latex_fractions():
    res = evaluate_latex(r"\frac{3}{4} + \sqrt{16}")
    assert res["status"] == "success"
    assert res["exact_text"] == "19/4"
    assert res["numeric_approximation"] == 4.75
    assert res["is_rational"] is True
    assert res["is_integer"] is False


def test_evaluate_latex_complex_fraction():
    res = evaluate_latex(r"\frac{3491 \times 18}{7}")
    assert res["status"] == "success"
    assert res["exact_text"] == "62838/7"
    assert res["numeric_approximation"] == 8976.8571428571


def test_evaluate_latex_calculus_integral():
    res = evaluate_latex(r"\int_{0}^{\pi} \sin(x) \, dx")
    assert res["status"] == "success"
    assert res["exact_text"] == "2"
    assert res["numeric_approximation"] == 2.0
    assert res["is_integer"] is True


def test_evaluate_latex_differential():
    res = evaluate_latex(r"\int_0^1 x \, \mathrm{d}x")
    assert res["status"] == "success"
    assert res["exact_text"] == "1/2"
    assert res["numeric_approximation"] == 0.5


def test_evaluate_latex_trigonometry():
    res = evaluate_latex(r"\sin\left(\frac{\pi}{2}\right)")
    assert res["status"] == "success"
    assert res["exact_text"] == "1"
    assert res["numeric_approximation"] == 1.0


def test_evaluate_latex_boolean_equality():
    res_true = evaluate_latex("2 + 2 = 4")
    assert res_true["status"] == "success"
    assert res_true["boolean_value"] is True

    res_false = evaluate_latex("2 + 2 = 5")
    assert res_false["status"] == "success"
    assert res_false["boolean_value"] is False


def test_evaluate_latex_algebraic_expression():
    res = evaluate_latex(r"2x + 5")
    assert res["status"] == "success"
    assert "x" in res["free_variables"]
    assert res["numeric_approximation"] is None


def test_solve_equation_linear():
    res = solve_equation("2x + 5 = 15")
    assert res["status"] == "success"
    assert res["solutions_numeric"] == [5.0]


def test_solve_equation_quadratic():
    res = solve_equation("x^2 - 5x + 6 = 0")
    assert res["status"] == "success"
    assert sorted(res["solutions_numeric"]) == [2.0, 3.0]


def test_solve_equation_latex_format():
    res = solve_equation(r"\frac{x}{3} = 4")
    assert res["status"] == "success"
    assert res["solutions_numeric"] == [12.0]


def test_solve_equation_specified_variable():
    res = solve_equation("2*a + 4 = 10", variable="a")
    assert res["status"] == "success"
    assert res["variable_solved"] == "a"
    assert res["solutions_numeric"] == [3.0]


def test_evaluate_expression_percentages():
    res = evaluate_expression("15% of 850")
    assert res["status"] == "success"
    assert res["exact_text"] == "255/2"
    assert res["numeric_approximation"] == 127.5


def test_evaluate_expression_powers_and_roots():
    res = evaluate_expression("sqrt(256) + 2^5")
    assert res["status"] == "success"
    assert res["exact_text"] == "48"
    assert res["numeric_approximation"] == 48.0


def test_evaluate_expression_arithmetic():
    res = evaluate_expression("(453 * 12) / (7 + 3)")
    assert res["status"] == "success"
    assert res["exact_text"] == "2718/5"
    assert res["numeric_approximation"] == 543.6
