"""Universal physical constants 

Categorized into:
1. EXACT_SI: Mathematically and legally defined by SI 2019 (zero uncertainty).
2. EMPIRICAL_CODATA: Measured physical quantities subject to scientific updates.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import sympy as sp


@dataclass(frozen=True)
class PhysicalConstant:
    symbol: str
    latex: str
    name: str
    value: Any
    unit: str
    category: str  # "EXACT_SI" or "EMPIRICAL_CODATA"
    source: str
    description: str


# Reference values matching symbols_encyclopedia.md & CODATA 2022 / SI 2019
CONSTANTS_CATALOG: Dict[str, PhysicalConstant] = {
    # 1. Speed of Causality / Light (Exact by SI definition 1983)
    "c": PhysicalConstant(
        symbol="c",
        latex=r"c",
        name="Speed of Causality / Light in Vacuum",
        value=sp.Integer(299792458),
        unit="m/s",
        category="EXACT_SI",
        source="BIPM SI Brochure (9th Edition)",
        description="Universal speed limit of causality and space-time conversion factor.",
    ),
    # 2. Reduced Planck Constant (Exact by SI definition 2019 via h / 2pi)
    "hbar": PhysicalConstant(
        symbol="hbar",
        latex=r"\hbar",
        name="Reduced Planck Constant (Dirac's h-bar)",
        value=sp.Rational(662607015, 10**43) / (2 * sp.pi),
        unit="J*s",
        category="EXACT_SI",
        source="BIPM / SI Definition 2019 (h / 2*pi)",
        description="Quantum graininess of phase space and scale of quantum action.",
    ),
    # Planck Constant (Exact by SI definition 2019)
    "h": PhysicalConstant(
        symbol="h",
        latex=r"h",
        name="Planck Constant",
        value=sp.Rational(662607015, 10**42),
        unit="J*s",
        category="EXACT_SI",
        source="BIPM SI Definition 2019 (6.62607015e-34 J*s)",
        description="Fundamental quantum of electromagnetic action.",
    ),
    # 3. Gravitational Coupling Constant (Empirical - CODATA 2022)
    "G": PhysicalConstant(
        symbol="G",
        latex=r"G",
        name="Newtonian Constant of Gravitation",
        value=sp.Float("6.67430e-11"),
        unit="m^3/(kg*s^2)",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Stiffness of spacetime curvature under mass-energy distribution.",
    ),
    # 4. Boltzmann Constant (Exact by SI definition 2019)
    "k_B": PhysicalConstant(
        symbol="k_B",
        latex=r"k_B",
        name="Boltzmann Constant",
        value=sp.Rational(1380649, 10**29),
        unit="J/K",
        category="EXACT_SI",
        source="BIPM SI Definition 2019 (1.380649e-23 J/K)",
        description="Conversion factor between macroscopic temperature and microscopic kinetic energy.",
    ),
    "k": PhysicalConstant(
        symbol="k",
        latex=r"k",
        name="Boltzmann Constant (shorthand)",
        value=sp.Rational(1380649, 10**29),
        unit="J/K",
        category="EXACT_SI",
        source="BIPM SI Definition 2019",
        description="Conversion factor between temperature and microstate entropy.",
    ),
    # 5. Fine-Structure Constant (Empirical - CODATA 2022)
    "alpha": PhysicalConstant(
        symbol="alpha",
        latex=r"\alpha",
        name="Fine-Structure Constant",
        value=sp.Rational(1, 1) / sp.Float("137.035999084"),
        unit="dimensionless",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Electromagnetic coupling strength in Quantum Electrodynamics (QED).",
    ),
    # Elementary Electric Charge (Exact by SI definition 2019)
    "q_e": PhysicalConstant(
        symbol="q_e",
        latex=r"e",
        name="Elementary Charge",
        value=sp.Rational(1602176634, 10**28),
        unit="C",
        category="EXACT_SI",
        source="BIPM SI Definition 2019 (1.602176634e-19 C)",
        description="Electric charge carried by a single proton/electron.",
    ),
    # Vacuum Permittivity (Electric Constant - Derived / Empirical CODATA 2022)
    "eps_0": PhysicalConstant(
        symbol="eps_0",
        latex=r"\varepsilon_0",
        name="Vacuum Permittivity / Electric Constant",
        value=sp.Float("8.8541878128e-12"),
        unit="F/m",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Capability of vacuum to permit electric field lines.",
    ),
    # Vacuum Permeability (Magnetic Constant - Derived / Empirical CODATA 2022)
    "mu_0": PhysicalConstant(
        symbol="mu_0",
        latex=r"\mu_0",
        name="Vacuum Permeability / Magnetic Constant",
        value=sp.Float("1.25663706212e-6"),
        unit="N/A^2",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Capability of vacuum to support magnetic field lines.",
    ),
    # Electron Rest Mass (CODATA 2022)
    "m_e": PhysicalConstant(
        symbol="m_e",
        latex=r"m_e",
        name="Electron Rest Mass",
        value=sp.Float("9.1093837015e-31"),
        unit="kg",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Rest mass of an electron.",
    ),
    # Proton Rest Mass (CODATA 2022)
    "m_p": PhysicalConstant(
        symbol="m_p",
        latex=r"m_p",
        name="Proton Rest Mass",
        value=sp.Float("1.67262192369e-27"),
        unit="kg",
        category="EMPIRICAL_CODATA",
        source="CODATA 2022 (NIST)",
        description="Rest mass of a proton.",
    ),
    # Avogadro Constant (Exact by SI definition 2019)
    "N_A": PhysicalConstant(
        symbol="N_A",
        latex=r"N_A",
        name="Avogadro Constant",
        value=sp.Integer(602214076) * (sp.Integer(10) ** 15),
        unit="mol^-1",
        category="EXACT_SI",
        source="BIPM SI Definition 2019 (6.02214076e23 mol^-1)",
        description="Number of constituent particles per mole.",
    ),
    # Molar Gas Constant (Exact: R = N_A * k_B)
    "R_gas": PhysicalConstant(
        symbol="R_gas",
        latex=r"R",
        name="Molar Gas Constant",
        value=sp.Rational(831446261815324, 10**14),
        unit="J/(mol*K)",
        category="EXACT_SI",
        source="BIPM / Derived from N_A * k_B",
        description="Ideal gas law constant relating pressure, volume, temperature, and moles.",
    ),
}

# LaTeX symbol to constant symbol aliases
LATEX_PHYSICS_ALIAS_MAP: Dict[str, str] = {
    "c": "c",
    "hbar": "hbar",
    r"\hbar": "hbar",
    "h": "h",
    "G": "G",
    "k_B": "k_B",
    "k_{B}": "k_B",
    "k": "k_B",
    "alpha": "alpha",
    r"\alpha": "alpha",
    "varepsilon_0": "eps_0",
    "varepsilon_{0}": "eps_0",
    r"\varepsilon_0": "eps_0",
    "mu_0": "mu_0",
    "mu_{0}": "mu_0",
    r"\mu_0": "mu_0",
    "m_e": "m_e",
    "m_{e}": "m_e",
    "m_p": "m_p",
    "m_{p}": "m_p",
    "N_A": "N_A",
    "N_{A}": "N_A",
}


def get_physics_constant(key: str) -> Optional[PhysicalConstant]:
    """Retrieve metadata and exact value for a physical constant."""
    canonical_key = LATEX_PHYSICS_ALIAS_MAP.get(key, key)
    return CONSTANTS_CATALOG.get(canonical_key)


def get_physics_substitution_dict() -> Dict[sp.Symbol, Any]:
    """Generate a SymPy substitution dictionary mapping symbols to physical values."""
    sub_dict = {}
    for key, const in CONSTANTS_CATALOG.items():
        sub_dict[sp.Symbol(key)] = const.value
        if "_" in key:
            base, sub = key.split("_", 1)
            sub_dict[sp.Symbol(f"{base}_{{{sub}}}")] = const.value

    # Specific LaTeX parser symbol representations
    sub_dict[sp.Symbol("hbar")] = CONSTANTS_CATALOG["hbar"].value
    sub_dict[sp.Symbol("varepsilon_{0}")] = CONSTANTS_CATALOG["eps_0"].value
    sub_dict[sp.Symbol("epsilon_{0}")] = CONSTANTS_CATALOG["eps_0"].value
    sub_dict[sp.Symbol("mu_{0}")] = CONSTANTS_CATALOG["mu_0"].value
    sub_dict[sp.Symbol("k_{B}")] = CONSTANTS_CATALOG["k_B"].value
    sub_dict[sp.Symbol("m_{e}")] = CONSTANTS_CATALOG["m_e"].value
    sub_dict[sp.Symbol("m_{p}")] = CONSTANTS_CATALOG["m_p"].value
    sub_dict[sp.Symbol("N_{A}")] = CONSTANTS_CATALOG["N_A"].value
    return sub_dict
