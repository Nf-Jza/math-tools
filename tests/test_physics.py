"""Unit tests for physics calculations and universal physical constants."""

from math_tools.engine import evaluate_expression, evaluate_latex, query_physics_constant


def test_einstein_mass_energy():
    # E = m * c^2 for 1 gram (0.001 kg)
    res = evaluate_latex(
        r"m c^2",
        use_physics=True,
        variables={"m": 0.001},
    )
    assert res["status"] == "success"
    # ~8.98755e13 Joules
    assert abs(res["numeric_approximation"] - 89875517873681.77) < 1.0


def test_maxwell_speed_of_light_relation():
    # c = 1 / sqrt(eps_0 * mu_0)
    res = evaluate_latex(
        r"\frac{1}{\sqrt{\varepsilon_0 \mu_0}}",
        use_physics=True,
    )
    assert res["status"] == "success"
    assert abs(res["numeric_approximation"] - 299792458.0) < 1.0


def test_gravitational_surface_weight():
    # Weight of 70kg person on Earth: F = G * M * m / R^2
    # Earth mass M = 5.9722e24 kg, Earth radius R = 6.371e6 m
    res = evaluate_expression(
        "(G * M * m) / (R^2)",
        use_physics=True,
        variables={"M": 5.9722e24, "m": 70, "R": 6.371e6},
    )
    assert res["status"] == "success"
    # Expected: ~686.6 N
    assert abs(res["numeric_approximation"] - 686.6) < 1.0


def test_query_physics_constants():
    c_info = query_physics_constant("c")
    assert c_info["status"] == "success"
    assert c_info["numeric_value"] == 299792458.0
    assert c_info["category"] == "EXACT_SI"
    assert c_info["unit"] == "m/s"

    g_info = query_physics_constant("G")
    assert g_info["status"] == "success"
    assert g_info["category"] == "EMPIRICAL_CODATA"
    assert "CODATA" in g_info["source"]
