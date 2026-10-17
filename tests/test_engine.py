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


def test_hyperelliptic_integral_numerical_fallback():
    # Definite integral with hyperelliptic radical where symbolic Risch spins
    res_1_2 = evaluate_latex(
        r"\int_{1}^{2} \frac{x^2-2}{(x^2+2) \sqrt{x^4+4}} \, dx",
        timeout_seconds=5.0,
    )
    assert res_1_2["status"] == "success"
    assert res_1_2["is_number"] is True
    # Closed form is 1/2*acos(2/3) - 1/2*acos(2/3) = 0
    assert abs(res_1_2["numeric_approximation"]) < 1e-6

    res_0_1 = evaluate_latex(
        r"\int_{0}^{1} \frac{x^2-2}{(x^2+2) \sqrt{x^4+4}} \, dx",
        timeout_seconds=5.0,
    )
    assert res_0_1["status"] == "success"
    assert res_0_1["is_number"] is True
    assert abs(res_0_1["numeric_approximation"] - (-0.3648638281)) < 1e-6


def test_inverse_trig_derivative_algebraic():
    res = evaluate_latex(r"\frac{d}{dx} \left( \frac{1}{2} \arccos\left(\frac{2x}{x^2+2}\right) \right)")
    assert res["status"] == "success"
    assert "x" in res["free_variables"]
    # Verify derivative matches algebraic form at test point x = 0.5
    res_at_point = evaluate_latex(
        r"\frac{d}{dx} \left( \frac{1}{2} \arccos\left(\frac{2x}{x^2+2}\right) \right)",
        variables={"x": 0.5},
    )
    assert res_at_point["status"] == "success"
    assert abs(res_at_point["numeric_approximation"] - (-0.3858858409)) < 1e-6


def test_custom_timeout_seconds_parameter():
    # Verify timeout_seconds operates as expected
    with pytest.raises(Exception):
        evaluate_expression("999999^999999", timeout_seconds=0.2)

    res = evaluate_latex(r"\frac{1}{2} + \frac{1}{3}", timeout_seconds=10.0)
    assert res["status"] == "success"
    assert res["exact_text"] == "5/6"

