"""Unit tests for physics calculations and universal physical constants."""

import pytest
import sympy as sp

from math_tools.engine import evaluate_expression, evaluate_latex, query_physics_constant
from math_tools.physics import CONSTANTS_CATALOG


@pytest.mark.parametrize(
    ("symbol", "reference_value", "unit", "category"),
    [
        ("c", 299792458.0, "m/s", "EXACT_SI"),
        ("h", 6.62607015e-34, "J*s", "EXACT_SI"),
        ("hbar", 1.0545718176461565e-34, "J*s", "EXACT_SI"),
        ("G", 6.67430e-11, "m^3/(kg*s^2)", "EMPIRICAL_CODATA"),
        ("k_B", 1.380649e-23, "J/K", "EXACT_SI"),
        ("k", 1.380649e-23, "J/K", "EXACT_SI"),
        ("alpha", 1.0 / 137.035999177, "dimensionless", "EMPIRICAL_CODATA"),
        ("q_e", 1.602176634e-19, "C", "EXACT_SI"),
        ("eps_0", 8.8541878188e-12, "F/m", "EMPIRICAL_CODATA"),
        ("mu_0", 1.25663706127e-6, "N/A^2", "EMPIRICAL_CODATA"),
        ("m_e", 9.1093837139e-31, "kg", "EMPIRICAL_CODATA"),
        ("m_p", 1.67262192595e-27, "kg", "EMPIRICAL_CODATA"),
        ("N_A", 6.02214076e23, "mol^-1", "EXACT_SI"),
        ("R_gas", 8.31446261815324, "J/(mol*K)", "EXACT_SI"),
    ],
)
def test_catalog_reference_values_and_metadata(symbol, reference_value, unit, category):
    constant = CONSTANTS_CATALOG[symbol]

    # Zero absolute tolerance is essential for subatomic quantities: pytest's
    # default 1e-12 would accept zero or a wrong exponent for several constants.
    assert float(constant.value.evalf(17)) == pytest.approx(
        reference_value, rel=1e-14, abs=0.0
    )
    assert constant.symbol == symbol
    assert constant.unit == unit
    assert constant.category == category
    assert isinstance(constant.value, sp.Expr)
    if category == "EMPIRICAL_CODATA":
        assert isinstance(constant.value, sp.Float)
        assert constant.source == "CODATA 2022 (NIST)"
    else:
        assert not constant.value.has(sp.Float)
        assert "BIPM" in constant.source


def test_catalog_reduced_planck_constant_is_exactly_derived_from_h():
    h = CONSTANTS_CATALOG["h"].value
    hbar = CONSTANTS_CATALOG["hbar"].value

    assert h == sp.Rational(662607015, 10**42)
    assert 2 * sp.pi * hbar == h


def test_catalog_gas_constant_is_exactly_derived_from_avogadro_and_boltzmann():
    gas_constant = CONSTANTS_CATALOG["R_gas"].value

    assert gas_constant == CONSTANTS_CATALOG["N_A"].value * CONSTANTS_CATALOG["k_B"].value
    assert gas_constant == sp.Rational("8.31446261815324")
    assert CONSTANTS_CATALOG["k"].value == CONSTANTS_CATALOG["k_B"].value


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
