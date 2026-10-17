"""Deterministic mathematics and symbolic execution engine."""

import ast
import math
import signal
import sys
from typing import Any, Dict, List, Optional
import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from math_tools.guards import (
    DEFAULT_TIMEOUT_SECONDS,
    clamp_timeout,
    run_with_timeout,
    validate_input_length,
)
from math_tools.physics import (
    CONSTANTS_CATALOG,
    get_physics_constant,
    get_physics_substitution_dict,
)
from math_tools.sanitizer import sanitize_expression, sanitize_latex

# Canonical mathematical constant mappings to upgrade free symbols to true constants
CONSTANT_SUBSTITUTIONS = {
    sp.Symbol("pi"): sp.pi,
    sp.Symbol("e"): sp.E,
}

# Whitelist of allowed functions in standard expression evaluation
ALLOWED_MATH_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "sqrt", "cbrt", "exp", "log", "ln", "log10", "log2",
    "abs", "factorial", "gamma", "round", "floor", "ceil",
    "min", "max"
}

# Safe AST nodes for mathematical expressions
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,  # Literals: numbers, etc.
    ast.Name,      # Symbols: x, pi, etc.
    ast.Call,      # Function calls: sin(x)
    ast.Load,      # Variable context
    # Allowed operators:
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.UAdd, ast.USub,
)

SAFE_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

SAFE_LOCAL_DICT = {
    "Integer": sp.Integer,
    "Symbol": sp.Symbol,
    "Rational": sp.Rational,
    "Float": sp.Float,
    "pi": sp.pi,
    "e": sp.E,
    "E": sp.E,
    "I": sp.I,
    "sqrt": sp.sqrt,
    "cbrt": sp.cbrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "sec": sp.sec,
    "csc": sp.csc,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "abs": sp.Abs,
    "factorial": sp.factorial,
    "gamma": sp.gamma,
    "floor": sp.floor,
    "ceiling": sp.ceiling,
    "ceil": sp.ceiling,
}


class SymbolicBudgetExceeded(BaseException):
    """Raised when symbolic algorithm exceeds internal allocation budget."""


def _is_definite_numeric_integral(expr: Any) -> bool:
    """Check if an expression contains definite integrals with numeric limits and no free symbols."""
    if not hasattr(expr, "has") or not expr.has(sp.Integral):
        return False
    integrals = expr.atoms(sp.Integral)
    for integ in integrals:
        if not hasattr(integ, "limits") or not integ.limits:
            return False
        for lim in integ.limits:
            if len(lim) != 3 or not lim[1].is_number or not lim[2].is_number:
                return False
        if integ.free_symbols:
            return False
    return True


def _evaluate_symbolic_bounded(expr: Any, timeout_budget: float) -> Any:
    """Attempt symbolic evaluation within an internal time budget, falling back gracefully."""
    if not hasattr(expr, "doit") and not isinstance(expr, sp.Integral):
        return expr

    # Use ITIMER_REAL on POSIX systems to enforce internal symbolic budget
    if sys.platform != "win32":
        def _handler(signum, frame):
            raise SymbolicBudgetExceeded()

        budget = max(0.2, min(timeout_budget * 0.4, 1.5))
        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, budget)
        try:
            if isinstance(expr, sp.Integral):
                try:
                    res_manual = sp.integrate(expr.function, *expr.limits, manual=True)
                    if not res_manual.has(sp.Integral):
                        signal.setitimer(signal.ITIMER_REAL, 0)
                        return res_manual
                except SymbolicBudgetExceeded:
                    raise
                except Exception:
                    pass
            res = expr.doit()
            signal.setitimer(signal.ITIMER_REAL, 0)
            return res
        except SymbolicBudgetExceeded:
            signal.setitimer(signal.ITIMER_REAL, 0)
            return expr
        except Exception:
            signal.setitimer(signal.ITIMER_REAL, 0)
            return expr
        finally:
            signal.signal(signal.SIGALRM, old_handler)
    else:
        try:
            return expr.doit()
        except Exception:
            return expr


def validate_math_ast(expression_str: str) -> None:
    """Validate that an expression contains only benign mathematical syntax."""
    try:
        tree = ast.parse(expression_str, mode="eval")
    except Exception as exc:
        raise ValueError(f"Syntax error in expression: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(
                f"Security or syntax restriction: Disallowed expression element '{type(node).__name__}'."
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Disallowed complex or chained function call.")
            if node.func.id not in ALLOWED_MATH_FUNCTIONS:
                raise ValueError(f"Disallowed mathematical function: '{node.func.id}'.")


def _safe_float(expr: Any, precision: int = 10) -> Optional[float]:
    """Safely convert a SymPy expression to a Python float, or None if non-real/symbolic."""
    try:
        if hasattr(expr, "is_real") and expr.is_real is False:
            return None
        try:
            f_val = float(expr)
        except (TypeError, ValueError):
            evalf_val = expr.evalf(precision) if hasattr(expr, "evalf") else expr
            f_val = float(evalf_val)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return round(f_val, precision) if precision > 0 else f_val
    except Exception:
        return None


def _parse_latex_expression(clean_latex: str) -> Any:
    """Parse a sanitized LaTeX string with strict checking and multi-backend fallbacks."""
    # 1. If matrix or array syntax is detected, prioritize Lark parser
    is_matrix = any(k in clean_latex for k in ("matrix", "array", r"\\", "&"))
    if is_matrix:
        try:
            return parse_latex(clean_latex, backend="lark")
        except Exception:
            pass

    # 2. Try strict ANTLR
    try:
        return parse_latex(clean_latex, strict=True)
    except Exception:
        pass

    # 3. Try Lark parser
    try:
        return parse_latex(clean_latex, backend="lark")
    except Exception:
        pass

    # 4. Try non-strict ANTLR
    try:
        return parse_latex(clean_latex, strict=False)
    except Exception:
        pass

    # 5. Fallback via safe math parser
    validate_math_ast(clean_latex)
    return parse_expr(
        clean_latex,
        local_dict=SAFE_LOCAL_DICT,
        global_dict={"__builtins__": {}},
        transformations=SAFE_TRANSFORMATIONS,
        evaluate=True,
    )


def _parse_equation(raw_eq: str) -> sp.Eq:
    """Parse a mathematical equation string into a SymPy Eq object."""
    clean_latex = sanitize_latex(raw_eq)

    # 1. Try strict LaTeX parse directly
    try:
        parsed = _parse_latex_expression(clean_latex)
        if isinstance(parsed, sp.Eq):
            return parsed
    except Exception:
        pass

    # 2. Check for equality sign
    if "=" in clean_latex:
        parts = clean_latex.split("=", 1)
        lhs_str, rhs_str = parts[0].strip(), parts[1].strip()

        lhs = None
        rhs = None

        for parser in [
            _parse_latex_expression,
            lambda s: parse_expr(
                s,
                local_dict=SAFE_LOCAL_DICT,
                global_dict={"__builtins__": {}},
                transformations=SAFE_TRANSFORMATIONS,
                evaluate=True,
            ),
        ]:
            if lhs is None:
                try:
                    lhs = parser(lhs_str)
                except Exception:
                    pass
            if rhs is None:
                try:
                    rhs = parser(rhs_str)
                except Exception:
                    pass

        if lhs is not None and rhs is not None:
            return sp.Eq(lhs, rhs)

    # 3. No equality sign or fallback: treat expression as expr = 0
    clean_expr = sanitize_expression(raw_eq)
    expr = None
    for parser in [
        _parse_latex_expression,
        lambda s: parse_expr(
            s,
            local_dict=SAFE_LOCAL_DICT,
            global_dict={"__builtins__": {}},
            transformations=SAFE_TRANSFORMATIONS,
            evaluate=True,
        ),
    ]:
        try:
            expr = parser(clean_expr)
            break
        except Exception:
            pass

    if expr is not None:
        return sp.Eq(expr, 0)

    raise ValueError(f"Could not parse '{raw_eq}' into a valid equation.")


def _evaluate_latex_worker(
    latex_str: str,
    precision: int,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_budget: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Core synchronous worker for LaTeX evaluation."""
    validate_input_length(latex_str)
    clean = sanitize_latex(latex_str)
    if not clean:
        raise ValueError("Input LaTeX string is empty after sanitization.")

    parsed = _parse_latex_expression(clean)

    # Build active substitution table
    active_subs = dict(CONSTANT_SUBSTITUTIONS)
    if use_physics:
        active_subs.update(get_physics_substitution_dict())
    if variables:
        for k, v in variables.items():
            active_subs[sp.Symbol(k)] = sp.sympify(v)

    # Case 1: Boolean equality test (e.g. 2 + 2 = 4)
    if isinstance(parsed, (bool, sp.logic.boolalg.BooleanAtom)):
        return {
            "status": "success",
            "type": "boolean",
            "input_latex": clean,
            "boolean_value": bool(parsed),
            "exact_text": str(bool(parsed)),
        }

    # Case 2: Equation parsed as Eq (e.g. x + 2 = 5)
    if isinstance(parsed, sp.Eq):
        lhs_val = parsed.lhs.subs(active_subs).doit()
        rhs_val = parsed.rhs.subs(active_subs).doit()
        is_identical = lhs_val == rhs_val
        return {
            "status": "success",
            "type": "equation",
            "input_latex": clean,
            "equation_latex": sp.latex(parsed),
            "lhs_exact": str(lhs_val),
            "rhs_exact": str(rhs_val),
            "is_equal": bool(is_identical) if (lhs_val.is_number and rhs_val.is_number) else None,
        }

    # Case 3: Matrix object
    if isinstance(parsed, (sp.MatrixBase, sp.Matrix)):
        det_val = _safe_float(parsed.det(), precision) if parsed.is_square else None
        trace_val = _safe_float(parsed.trace(), precision) if parsed.is_square else None
        return {
            "status": "success",
            "type": "matrix",
            "input_latex": clean,
            "shape": list(parsed.shape),
            "exact_latex": sp.latex(parsed),
            "matrix_data": parsed.tolist(),
            "determinant": det_val,
            "trace": trace_val,
        }

    # Case 4: Standard mathematical expression
    subbed = parsed.subs(active_subs)
    evaluated = _evaluate_symbolic_bounded(subbed, timeout_budget=timeout_budget)
    simplified = sp.simplify(evaluated) if hasattr(evaluated, "simplify") else evaluated

    is_num = bool(simplified.is_number)
    is_rat = bool(simplified.is_rational) if is_num else False
    is_int = bool(simplified.is_integer) if is_num else False
    is_real = bool(simplified.is_real) if is_num else False

    # Check for definite numeric integral fallback
    if not is_num and _is_definite_numeric_integral(simplified):
        is_num = True

    numeric_val = _safe_float(simplified, precision) if is_num else None
    free_vars = sorted([str(s) for s in simplified.free_symbols])

    return {
        "status": "success",
        "type": "expression",
        "input_latex": clean,
        "exact_latex": sp.latex(simplified),
        "exact_text": str(simplified),
        "numeric_approximation": numeric_val,
        "is_number": is_num,
        "is_integer": is_int,
        "is_rational": is_rat,
        "is_real": is_real,
        "free_variables": free_vars,
    }


def _solve_equation_worker(equation_str: str, variable: Optional[str]) -> Dict[str, Any]:
    """Core synchronous worker for solving equations."""
    validate_input_length(equation_str)
    eq = _parse_equation(equation_str)

    all_symbols = sorted(list(eq.free_symbols), key=lambda s: s.name)
    if not all_symbols:
        is_true = bool(eq.lhs == eq.rhs)
        return {
            "status": "success",
            "equation_latex": sp.latex(eq),
            "is_identity": is_true,
            "solutions_latex": [],
            "solutions_text": [],
            "solutions_numeric": [],
        }

    target_var = sp.Symbol(variable) if variable else all_symbols[0]
    solutions = sp.solve(eq, target_var)

    solutions_latex: List[str] = []
    solutions_text: List[str] = []
    solutions_numeric: List[Optional[float]] = []

    for sol in solutions:
        simplified_sol = sp.simplify(sol)
        solutions_latex.append(sp.latex(simplified_sol))
        solutions_text.append(str(simplified_sol))
        solutions_numeric.append(_safe_float(simplified_sol))

    return {
        "status": "success",
        "equation_latex": sp.latex(eq),
        "variable_solved": str(target_var),
        "solutions_count": len(solutions),
        "solutions_latex": solutions_latex,
        "solutions_text": solutions_text,
        "solutions_numeric": solutions_numeric,
    }


def _evaluate_expression_worker(
    expression_str: str,
    precision: int,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_budget: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Core synchronous worker for evaluating general non-LaTeX expressions."""
    validate_input_length(expression_str)
    clean = sanitize_expression(expression_str)
    if not clean:
        raise ValueError("Expression is empty after sanitization.")

    # Strict AST validation preventing remote code execution
    validate_math_ast(clean)

    active_local_dict = dict(SAFE_LOCAL_DICT)
    if use_physics:
        for k, const in CONSTANTS_CATALOG.items():
            active_local_dict[k] = const.value
    if variables:
        for k, v in variables.items():
            active_local_dict[k] = sp.sympify(v)

    parsed = parse_expr(
        clean,
        local_dict=active_local_dict,
        global_dict={"__builtins__": {}},
        transformations=SAFE_TRANSFORMATIONS,
        evaluate=True,
    )

    active_subs = dict(CONSTANT_SUBSTITUTIONS)
    if use_physics:
        active_subs.update(get_physics_substitution_dict())
    if variables:
        for k, v in variables.items():
            active_subs[sp.Symbol(k)] = sp.sympify(v)

    subbed = parsed.subs(active_subs)
    evaluated = _evaluate_symbolic_bounded(subbed, timeout_budget=timeout_budget)
    simplified = sp.simplify(evaluated) if hasattr(evaluated, "simplify") else evaluated

    is_num = bool(simplified.is_number)
    is_rat = bool(simplified.is_rational) if is_num else False
    is_int = bool(simplified.is_integer) if is_num else False
    is_real = bool(simplified.is_real) if is_num else False

    if not is_num and _is_definite_numeric_integral(simplified):
        is_num = True

    numeric_val = _safe_float(simplified, precision) if is_num else None
    free_vars = sorted([str(s) for s in simplified.free_symbols])

    return {
        "status": "success",
        "input_expression": clean,
        "exact_text": str(simplified),
        "exact_latex": sp.latex(simplified),
        "numeric_approximation": numeric_val,
        "is_number": is_num,
        "is_integer": is_int,
        "is_rational": is_rat,
        "is_real": is_real,
        "free_variables": free_vars,
    }


def query_physics_constant(symbol: str) -> Dict[str, Any]:
    """Look up a universal physical constant with metadata, units, and source."""
    const = get_physics_constant(symbol)
    if not const:
        available = sorted(list(CONSTANTS_CATALOG.keys()))
        return {
            "status": "not_found",
            "symbol": symbol,
            "message": f"Constant '{symbol}' not found in catalog.",
            "available_constants": available,
        }
    return {
        "status": "success",
        "symbol": const.symbol,
        "name": const.name,
        "latex": const.latex,
        "exact_value_text": str(const.value),
        "numeric_value": float(const.value.evalf()) if hasattr(const.value, "evalf") else float(const.value),
        "unit": const.unit,
        "category": const.category,
        "source": const.source,
        "description": const.description,
    }


# Public API wrapped with process-isolated execution and timeout
def evaluate_latex(
    latex_str: str,
    precision: int = 10,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate a LaTeX mathematical expression with deterministic timeout."""
    validate_input_length(latex_str)
    budget = clamp_timeout(timeout_seconds if timeout_seconds is not None else timeout)
    return run_with_timeout(
        _evaluate_latex_worker,
        args=(latex_str, precision, use_physics, variables, budget),
        timeout_seconds=budget,
    )


def solve_equation(
    equation_str: str,
    variable: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Solve an equation deterministically with process-isolated timeout."""
    validate_input_length(equation_str)
    budget = clamp_timeout(timeout_seconds if timeout_seconds is not None else timeout)
    return run_with_timeout(
        _solve_equation_worker,
        args=(equation_str, variable),
        timeout_seconds=budget,
    )


def evaluate_expression(
    expression_str: str,
    precision: int = 10,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate a standard mathematical expression with deterministic timeout."""
    validate_input_length(expression_str)
    budget = clamp_timeout(timeout_seconds if timeout_seconds is not None else timeout)
    return run_with_timeout(
        _evaluate_expression_worker,
        args=(expression_str, precision, use_physics, variables, budget),
        timeout_seconds=budget,
    )
