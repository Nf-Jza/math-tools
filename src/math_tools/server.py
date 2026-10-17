"""FastMCP Stdio Server exposing deterministic mathematics and symbolic tools."""

import json
from typing import Any, Dict, Optional
from mcp.server.mcpserver import MCPServer

from math_tools.engine import (
    evaluate_expression as run_evaluate_expression,
    evaluate_latex as run_evaluate_latex,
    query_physics_constant,
    solve_equation as run_solve_equation,
)

server = MCPServer(
    name="math-tools",
    instructions=(
        "Deterministic mathematical and symbolic computation engine. "
        "Use these tools whenever calculating arithmetic, fractions, percentages, "
        "calculus, algebra, equations, or universal physical constants. "
        "Never calculate math internally in token predictions when these tools are available."
    ),
)


@server.tool(
    name="evaluate_latex",
    description=(
        "Deterministically evaluate a LaTeX mathematical expression, fraction, calculus integral, "
        "derivative, limit, summation, or matrix. Never guess math in text when this tool is available."
    ),
)
def evaluate_latex(
    latex: str,
    precision: int = 10,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> str:
    """Evaluate a LaTeX expression.

    Args:
        latex: Raw LaTeX math formula (e.g. r"\\frac{3}{4} + \\sqrt{16}", r"\\int_0^\\pi \\sin(x)dx").
        precision: Decimal precision digits for floating-point values (default 10).
        use_physics: If true, substitutes universal physical constants (c, hbar, G, k_B, alpha, etc.).
        variables: Optional mapping of variable symbols to values (e.g. {"m": 0.001}).
        timeout_seconds: Optional execution timeout budget in seconds (default 5.0, min 0.1, max 30.0).
    """
    try:
        result = run_evaluate_latex(
            latex_str=latex,
            precision=precision,
            use_physics=use_physics,
            variables=variables,
            timeout_seconds=timeout_seconds,
        )
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            indent=2,
        )


@server.tool(
    name="evaluate_expression",
    description=(
        "Deterministically evaluate a standard mathematical expression, percentage, "
        "arithmetic string, or power (e.g. '15% of 850', 'sqrt(256) + 2^5', '(453 * 12) / (7 + 3)')."
    ),
)
def evaluate_expression(
    expression: str,
    precision: int = 10,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> str:
    """Evaluate a standard mathematical expression.

    Args:
        expression: Mathematical expression string.
        precision: Decimal precision digits for floating-point values (default 10).
        use_physics: If true, substitutes universal physical constants.
        variables: Optional mapping of variable symbols to values.
        timeout_seconds: Optional execution timeout budget in seconds (default 5.0, min 0.1, max 30.0).
    """
    try:
        result = run_evaluate_expression(
            expression_str=expression,
            precision=precision,
            use_physics=use_physics,
            variables=variables,
            timeout_seconds=timeout_seconds,
        )
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            indent=2,
        )


@server.tool(
    name="solve_equation",
    description=(
        "Deterministically solve an algebraic equation or polynomial for exact and numeric roots "
        "(e.g. '2x + 5 = 15', 'x^2 - 5x + 6 = 0', r'\\frac{x}{3} = 4')."
    ),
)
def solve_equation(
    equation: str,
    variable: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> str:
    """Solve an equation for a variable.

    Args:
        equation: Algebraic equation string or LaTeX equation.
        variable: Target variable symbol to solve for (defaults to primary free symbol).
        timeout_seconds: Optional execution timeout budget in seconds (default 5.0, min 0.1, max 30.0).
    """
    try:
        result = run_solve_equation(
            equation_str=equation,
            variable=variable,
            timeout_seconds=timeout_seconds,
        )
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            indent=2,
        )


@server.tool(
    name="get_physics_constant",
    description=(
        "Look up exact definitions, numerical values, SI units, and CODATA references "
        "for universal physical constants (c, hbar, h, G, k_B, alpha, eps_0, mu_0, m_e, m_p, N_A, R_gas)."
    ),
)
def get_physics_constant(symbol: str) -> str:
    """Look up a universal physical constant.

    Args:
        symbol: Symbol identifier (e.g. 'c', 'hbar', 'G', 'k_B', 'alpha', 'eps_0', 'mu_0', 'm_e', 'm_p').
    """
    try:
        result = query_physics_constant(symbol=symbol)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            indent=2,
        )


def main() -> None:
    """Entrypoint to run the MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
