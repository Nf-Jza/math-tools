"""Deterministic mathematics and symbolic execution engine.

Plain expressions are built from a validated Python AST, never evaluated as Python.
``numeric_approximation`` is a finite, machine-precision convenience float (with
legacy decimal-place rounding for ordinary magnitudes). ``numeric_decimal`` is a
string evaluated to the requested 1--100 significant decimal digits, and is the
appropriate result for high precision, very small values, or float overflow.
"""

import ast
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import io
import keyword
import math
import re
import signal
import sys
import tokenize
from typing import Any, Dict, List, Optional

import sympy as sp
from sympy.parsing.latex import parse_latex

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

CONSTANT_SUBSTITUTIONS = {
    sp.Symbol("pi"): sp.pi,
    sp.Symbol("e"): sp.E,
}

def _math_round(value: sp.Expr, digits: sp.Expr = sp.Integer(0)) -> sp.Expr:
    """Round numerically but retain the exact decimal instead of a low-bit Float."""
    if not isinstance(digits, sp.Integer) or abs(digits) > MAX_PRECISION:
        raise ValueError("round digits must be an integer between -100 and 100.")
    return _decimal_rational(str(value.round(int(digits))))


MATH_CONSTANTS = {"pi": sp.pi, "e": sp.E, "E": sp.E, "I": sp.I}
MATH_FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "sqrt": sp.sqrt, "cbrt": sp.cbrt, "exp": sp.exp,
    "log": sp.log, "ln": sp.log,
    "log10": lambda value: sp.log(value, 10),
    "log2": lambda value: sp.log(value, 2),
    "abs": sp.Abs, "factorial": sp.factorial, "gamma": sp.gamma,
    "round": _math_round,
    "floor": sp.floor, "ceil": sp.ceiling, "ceiling": sp.ceiling,
    "min": sp.Min, "max": sp.Max,
}
ALLOWED_MATH_FUNCTIONS = frozenset(MATH_FUNCTIONS)
ALLOWED_AST_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
    ast.Call, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.UAdd, ast.USub,
)

MAX_PRECISION = 100
MAX_VARIABLES = 64
MAX_SYMBOL_LENGTH = 64
MAX_NUMERIC_LITERAL_LENGTH = 256
MAX_DECIMAL_EXPONENT = 1000
MAX_INTEGER_BITS = 4096
_SYMBOL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_DECIMAL_LITERAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_RESERVED_NAMES = frozenset(MATH_FUNCTIONS) | frozenset(MATH_CONSTANTS) | {
    "Integer", "Rational", "Float", "Symbol", "Number", "Function",
    "Matrix", "ImmutableMatrix", "Integral", "Derivative", "Sum", "Product",
    "Limit", "Eq", "S", "N", "True", "False", "None",
}


class SymbolicBudgetExceeded(BaseException):
    """Raised when symbolic algorithm exceeds internal allocation budget."""


def _validate_precision(precision: int) -> int:
    if type(precision) is not int or not 1 <= precision <= MAX_PRECISION:
        raise ValueError(f"precision must be an integer between 1 and {MAX_PRECISION}.")
    return precision


def _validate_symbol_name(name: str, *, allow_reserved: bool = False) -> None:
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= MAX_SYMBOL_LENGTH
        or not _SYMBOL_NAME.fullmatch(name)
        or "__" in name
        or keyword.iskeyword(name)
    ):
        raise ValueError("Variable names must be public ASCII identifiers of at most 64 characters.")
    if not allow_reserved and name in _RESERVED_NAMES:
        raise ValueError(f"Variable name '{name}' is reserved for a mathematical function or constant.")


def _decimal_rational(text: str) -> sp.Rational:
    """Construct an exact decimal using a literal-only grammar and integer arithmetic."""
    if len(text) > MAX_NUMERIC_LITERAL_LENGTH or not _DECIMAL_LITERAL.fullmatch(text):
        raise ValueError("Expected a bounded, finite decimal numeric literal.")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal numeric literal.") from exc
    sign, digits, exponent = value.as_tuple()
    if not value.is_finite() or abs(exponent) > MAX_DECIMAL_EXPONENT:
        raise ValueError(f"Decimal exponents must be between -{MAX_DECIMAL_EXPONENT} and {MAX_DECIMAL_EXPONENT}.")
    coefficient = int("".join(map(str, digits))) * (-1 if sign else 1)
    if exponent >= 0:
        return sp.Integer(coefficient * 10**exponent)
    return sp.Rational(coefficient, 10**(-exponent))


def _numeric_variable(value: Any) -> sp.Expr:
    """Accept finite real scalars, not expressions or strings to be sympified."""
    if isinstance(value, bool):
        raise ValueError("Boolean variable values are not numeric scalars.")
    if isinstance(value, int):
        if value.bit_length() > MAX_INTEGER_BITS:
            raise ValueError("Integer variable value is too large.")
        return sp.Integer(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Variable values must be finite.")
        return sp.Float(value)
    if isinstance(value, str):
        text = value.strip()
        if len(value) > MAX_NUMERIC_LITERAL_LENGTH:
            raise ValueError("Numeric variable literal is too long.")
        if "/" in text:
            parts = text.split("/")
            if len(parts) != 2:
                raise ValueError("Expected one numerator and denominator.")
            numerator, denominator = (_decimal_rational(part.strip()) for part in parts)
            if denominator == 0:
                raise ValueError("Variable denominator must be nonzero.")
            return numerator / denominator
        return _decimal_rational(text)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Variable values must be finite.")
        return _decimal_rational(str(value))
    if isinstance(value, Fraction):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_INTEGER_BITS:
            raise ValueError("Rational variable value is too large.")
        return sp.Rational(value.numerator, value.denominator)
    if isinstance(value, (sp.Integer, sp.Rational, sp.Float)):
        if value.is_finite is not True or value.is_real is not True:
            raise ValueError("Variable values must be finite real scalars.")
        if isinstance(value, sp.Rational):
            if max(int(value.p).bit_length(), int(value.q).bit_length()) > MAX_INTEGER_BITS:
                raise ValueError("Rational variable value is too large.")
        elif value._prec > MAX_INTEGER_BITS or abs(value) > 10**MAX_DECIMAL_EXPONENT:
            raise ValueError("Floating-point variable value is too large.")
        return value
    raise ValueError("Variable values must be finite real numeric scalars or numeric literals.")


def _validate_variables(variables: Optional[Dict[str, Any]]) -> Dict[str, sp.Expr]:
    if variables is None:
        return {}
    if not isinstance(variables, dict) or len(variables) > MAX_VARIABLES:
        raise ValueError(f"variables must be a mapping with at most {MAX_VARIABLES} entries.")
    result = {}
    for name, value in variables.items():
        _validate_symbol_name(name)
        result[name] = _numeric_variable(value)
    return result


def _validated_math_tree(expression_str: str) -> ast.Expression:
    """Reject all syntax except scalar arithmetic and explicitly named math calls."""
    if "#" in expression_str:
        raise ValueError("Comments are not mathematical syntax.")
    tree = ast.parse(expression_str, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Disallowed expression element '{type(node).__name__}'.")
        if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
            raise ValueError("Only real numeric literals are allowed in mathematical expressions.")
        if isinstance(node, ast.Name):
            _validate_symbol_name(node.id, allow_reserved=True)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in MATH_FUNCTIONS:
                raise ValueError("Only named, whitelisted mathematical function calls are allowed.")
            if node.keywords:
                raise ValueError("Keyword arguments are not allowed in mathematical calls.")
    return tree


def validate_math_ast(expression_str: str) -> None:
    """Validate plain mathematical syntax without executing or evaluating it."""
    try:
        _validated_math_tree(expression_str)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in expression: {exc}") from exc


def _normalize_factorials(text: str) -> str:
    """Translate postfix factorial atoms to whitelisted calls before AST parsing.

    Tokenization preserves string tokens for subsequent rejection; no substitution
    can turn quoted text, attribute access, or another forbidden AST into code.
    """
    if "!" not in text:
        return text
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError) as exc:
        raise ValueError("Invalid factorial expression.") from exc
    output = []
    previous_factorial = False
    for token in tokens:
        if token.type in (tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL, tokenize.ENCODING):
            continue
        if token.type == tokenize.ERRORTOKEN and token.string.isspace():
            continue
        if token.string != "!":
            output.append((token.type, token.string))
            previous_factorial = False
            continue
        if not output or previous_factorial:
            raise ValueError("Factorial requires a single preceding numeric expression.")
        start = len(output) - 1
        if output[start][1] == ")":
            depth = 1
            while start > 0 and depth:
                start -= 1
                if output[start][1] == ")":
                    depth += 1
                elif output[start][1] == "(":
                    depth -= 1
            if depth:
                raise ValueError("Unbalanced factorial parentheses.")
            if start > 0 and output[start - 1][0] == tokenize.NAME:
                start -= 1
        elif output[start][0] not in (tokenize.NUMBER, tokenize.NAME):
            raise ValueError("Invalid factorial operand.")
        output[start:] = [(tokenize.NAME, "factorial"), (tokenize.OP, "(")] + output[start:] + [(tokenize.OP, ")")]
        previous_factorial = True
    return tokenize.untokenize(output).strip()


def _parse_plain_expression(text: str) -> sp.Expr:
    """Recursively build SymPy values from an allowlisted AST, with exact decimals."""
    text = _normalize_factorials(text)
    tree = _validated_math_tree(text)

    def build(node: ast.AST) -> sp.Expr:
        if isinstance(node, ast.Constant):
            literal = ast.get_source_segment(text, node).replace("_", "")
            if len(literal) > MAX_NUMERIC_LITERAL_LENGTH:
                raise ValueError("Numeric literal is too long.")
            if type(node.value) is int:
                return sp.Integer(node.value)
            return _decimal_rational(literal)
        if isinstance(node, ast.Name):
            if node.id in MATH_CONSTANTS:
                return MATH_CONSTANTS[node.id]
            _validate_symbol_name(node.id)
            return sp.Symbol(node.id)
        if isinstance(node, ast.UnaryOp):
            operand = build(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.BinOp):
            left, right = build(node.left), build(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
            if isinstance(node.op, ast.Mod):
                return sp.Mod(left, right)
            if isinstance(node.op, ast.FloorDiv):
                return sp.floor(left / right)
        if isinstance(node, ast.Call):
            try:
                return MATH_FUNCTIONS[node.func.id](*(build(arg) for arg in node.args))
            except (TypeError, IndexError) as exc:
                raise ValueError(f"Invalid arguments to mathematical function '{node.func.id}'.") from exc
        raise ValueError("Unsupported mathematical expression.")

    return build(tree.body)


def _is_definite_numeric_integral(expr: Any) -> bool:
    """Identify closed definite integrals suitable for numerical quadrature."""
    if not hasattr(expr, "has") or not expr.has(sp.Integral) or expr.free_symbols:
        return False
    for integral in expr.atoms(sp.Integral):
        if not integral.limits:
            return False
        for limit in integral.limits:
            if len(limit) != 3 or not limit[1].is_number or not limit[2].is_number:
                return False
    return True


def _cheap_windows_integral(integral: sp.Integral) -> bool:
    """Conservatively recognize inexpensive symbolic cases without an alarm timer.

    Polynomial integrands, elementary functions of an affine argument, and a
    Gaussian retain exact answers. Other closed integrals go straight to evalf;
    a full symbolic integrator on Windows cannot honor an internal SIGALRM budget.
    """
    symbols = [limit[0] for limit in integral.limits]
    function = integral.function
    if function.is_polynomial(*symbols):
        return True
    if len(symbols) != 1 or function.func not in (sp.sin, sp.cos, sp.exp):
        return False
    argument = function.args[0]
    if not argument.is_polynomial(symbols[0]):
        return False
    degree = sp.degree(argument, symbols[0])
    return degree <= 1 or (function.func == sp.exp and degree == 2)


def _evaluate_symbolic_bounded(expr: Any, timeout_budget: float) -> Any:
    """Attempt symbolic evaluation within an internal budget, retaining fallbacks."""
    if not hasattr(expr, "doit"):
        return expr
    if sys.platform == "win32":
        if _is_definite_numeric_integral(expr):
            integrals = expr.atoms(sp.Integral)
            if not all(_cheap_windows_integral(integral) for integral in integrals):
                return expr
        try:
            return expr.doit()
        except Exception:
            return expr

    def _handler(signum, frame):
        raise SymbolicBudgetExceeded()

    budget = max(0.2, min(timeout_budget * 0.4, 1.5))
    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, budget)
    try:
        if isinstance(expr, sp.Integral):
            try:
                manual = sp.integrate(expr.function, *expr.limits, manual=True)
                if not manual.has(sp.Integral):
                    return manual
            except SymbolicBudgetExceeded:
                raise
            except Exception:
                pass
        return expr.doit()
    except (SymbolicBudgetExceeded, Exception):
        return expr
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def _safe_float(expr: Any, precision: int = 10) -> Optional[float]:
    """Return a finite convenience float, preserving tiny nonzero magnitudes.

    Ordinary values retain legacy decimal-place rounding. Small values use
    significant digits instead; callers needing more than machine precision or
    values outside the float range should use the ``numeric_decimal`` string.
    """
    try:
        if hasattr(expr, "is_real") and expr.is_real is False:
            return None
        value = float(expr)
        if not math.isfinite(value):
            return None
        if value == 0:
            # Do not misrepresent a nonzero value below the machine float range.
            is_zero = expr == 0 or getattr(expr, "is_zero", False) is True
            return 0.0 if is_zero else None
        if abs(value) < 10**(-precision / 2):
            return float(format(value, f".{precision}g"))
        return round(value, precision)
    except Exception:
        return None


def _numeric_results(expr: Any, precision: int) -> Dict[str, Any]:
    """Evaluate once with guard digits, then format the requested significant digits."""
    try:
        value = expr.evalf(max(17, precision))
        if value.is_real is not True or value.is_finite is not True or value.is_number is not True:
            raise ValueError("Not a finite real numeric value.")
        return {
            "numeric_approximation": _safe_float(value, precision),
            "numeric_decimal": str(value.evalf(precision)),
        }
    except Exception:
        return {"numeric_approximation": None, "numeric_decimal": None}


def _equation_sides(text: str) -> Optional[List[str]]:
    """Split only top-level equalities, not the limits of sums or products."""
    depth = 0
    positions = []
    for index, char in enumerate(text):
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif char == "=" and depth == 0:
            positions.append(index)
    if not positions:
        return None
    if len(positions) != 1:
        raise ValueError("An equation must contain exactly one equality.")
    position = positions[0]
    parts = [text[:position].strip(), text[position + 1:].strip()]
    if not all(parts):
        raise ValueError("An equation must contain two nonempty sides.")
    return parts


def _parse_latex_expression(clean_latex: str) -> Any:
    """Use the safe plain parser or full-input strict ANTLR/Lark LaTeX parsing.

    A syntactically valid but forbidden Python expression is never retried as
    LaTeX, where it might otherwise be reinterpreted as a harmless-looking prefix.
    """
    if _equation_sides(clean_latex) is not None:
        return _parse_equation(clean_latex)
    if "\\" not in clean_latex:
        plain = sanitize_expression(clean_latex)
        try:
            return _parse_plain_expression(plain)
        except SyntaxError:
            # Implicit products (2x) are LaTeX, not Python arithmetic syntax.
            pass
    if "__" in clean_latex or any(char in clean_latex for char in ('"', "'", "`")):
        raise ValueError("Quoted strings and private names are not mathematical input.")
    is_matrix = any(key in clean_latex for key in ("matrix", "array", r"\\", "&"))
    backends = ("lark", "antlr") if is_matrix else ("antlr", "lark")
    for backend in backends:
        try:
            parsed = parse_latex(clean_latex, strict=True, backend=backend)
            if isinstance(parsed, (sp.Basic, sp.MatrixBase)):
                return parsed
        except Exception:
            pass
    raise ValueError("Could not parse the complete mathematical input.")


def _parse_equation(raw_eq: str) -> sp.Equality:
    """Parse both sides safely, retaining equality instead of eager booleans."""
    clean = sanitize_latex(raw_eq)
    parts = _equation_sides(clean)
    if parts is not None:
        lhs, rhs = (_parse_latex_expression(part) for part in parts)
    else:
        lhs, rhs = _parse_latex_expression(clean), sp.Integer(0)
    if not isinstance(lhs, sp.Expr) or not isinstance(rhs, sp.Expr):
        raise ValueError("Equation sides must be scalar mathematical expressions.")
    return sp.Eq(lhs, rhs, evaluate=False)


def _active_substitutions(use_physics: bool, variables: Dict[str, sp.Expr]) -> Dict[Any, Any]:
    substitutions = dict(CONSTANT_SUBSTITUTIONS)
    if use_physics:
        substitutions.update(get_physics_substitution_dict())
    substitutions.update({sp.Symbol(name): value for name, value in variables.items()})
    return substitutions


def _substitute_after_derivatives(expr: Any, substitutions: Dict[Any, Any]) -> Any:
    """Differentiate in the original symbols before substituting evaluation points."""
    if expr.has(sp.Derivative):
        expr = expr.replace(
            lambda node: isinstance(node, sp.Derivative),
            lambda derivative: derivative.doit(),
        )
    return expr.subs(substitutions)


def _evaluate_scalar(expr: sp.Expr, substitutions: Dict[Any, Any], timeout_budget: float) -> sp.Expr:
    subbed = _substitute_after_derivatives(expr, substitutions)
    evaluated = _evaluate_symbolic_bounded(subbed, timeout_budget)
    # simplify(Integral(...)) can re-enter the very symbolic integration we skipped.
    if _is_definite_numeric_integral(evaluated):
        return evaluated
    return sp.simplify(evaluated)


def _scalar_result(expr: sp.Expr, precision: int) -> Dict[str, Any]:
    is_num = bool(expr.is_number) or _is_definite_numeric_integral(expr)
    numeric = _numeric_results(expr, precision) if is_num else {
        "numeric_approximation": None, "numeric_decimal": None,
    }
    return {
        "exact_latex": sp.latex(expr),
        "exact_text": str(expr),
        **numeric,
        "is_number": is_num,
        "is_integer": bool(expr.is_integer) if is_num else False,
        "is_rational": bool(expr.is_rational) if is_num else False,
        "is_real": bool(expr.is_real) if is_num else False,
        "free_variables": sorted(str(symbol) for symbol in expr.free_symbols),
    }


def _json_exact_cell(value: sp.Expr) -> Any:
    """Keep small integers numeric; encode other exact cells as lossless strings."""
    if isinstance(value, sp.Integer) and abs(value) <= 2**53 - 1:
        return int(value)
    return str(value)


def _evaluate_latex_worker(
    latex_str: str,
    precision: int,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_budget: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Core LaTeX worker; numeric_decimal uses significant, not fractional, digits."""
    validate_input_length(latex_str)
    _validate_precision(precision)
    validated_variables = _validate_variables(variables)
    clean = sanitize_latex(latex_str)
    if not clean:
        raise ValueError("Input LaTeX string is empty after sanitization.")
    parsed = _parse_latex_expression(clean)
    substitutions = _active_substitutions(use_physics, validated_variables)
    if isinstance(parsed, (bool, sp.logic.boolalg.BooleanAtom)):
        return {
            "status": "success", "type": "boolean", "input_latex": clean,
            "boolean_value": bool(parsed), "exact_text": str(bool(parsed)),
        }
    if isinstance(parsed, sp.Equality):
        lhs = _evaluate_scalar(parsed.lhs, substitutions, timeout_budget)
        rhs = _evaluate_scalar(parsed.rhs, substitutions, timeout_budget)
        equality = sp.Eq(lhs, rhs)
        if isinstance(equality, sp.logic.boolalg.BooleanAtom):
            return {
                "status": "success", "type": "boolean", "input_latex": clean,
                "boolean_value": bool(equality), "exact_text": str(bool(equality)),
            }
        return {
            "status": "success", "type": "equation", "input_latex": clean,
            "equation_latex": sp.latex(parsed),
            "lhs_exact": str(lhs), "rhs_exact": str(rhs),
            "is_equal": bool(lhs == rhs) if (lhs.is_number and rhs.is_number) else None,
        }
    if isinstance(parsed, sp.MatrixBase):
        matrix = parsed.applyfunc(lambda cell: _evaluate_scalar(cell, substitutions, timeout_budget))
        return {
            "status": "success", "type": "matrix", "input_latex": clean,
            "shape": list(matrix.shape), "exact_latex": sp.latex(matrix),
            "matrix_data": [[_json_exact_cell(cell) for cell in row] for row in matrix.tolist()],
            "determinant": _safe_float(matrix.det(), precision) if matrix.is_square else None,
            "trace": _safe_float(matrix.trace(), precision) if matrix.is_square else None,
        }
    if not isinstance(parsed, sp.Expr):
        raise ValueError("Input must be a scalar expression, equation, or matrix.")
    evaluated = _evaluate_scalar(parsed, substitutions, timeout_budget)
    return {
        "status": "success", "type": "expression", "input_latex": clean,
        **_scalar_result(evaluated, precision),
    }


def _solve_equation_worker(equation_str: str, variable: Optional[str]) -> Dict[str, Any]:
    """Solve equations, explicitly distinguishing identities and contradictions."""
    validate_input_length(equation_str)
    if variable is not None:
        _validate_symbol_name(variable)
    equation = _parse_equation(equation_str)
    symbols = sorted(equation.free_symbols, key=lambda symbol: symbol.name)
    target = sp.Symbol(variable) if variable else (symbols[0] if symbols else None)
    residual = sp.simplify(equation.lhs - equation.rhs)
    identity = residual == 0
    contradiction = not identity and not residual.free_symbols
    base = {
        "status": "success", "equation_latex": sp.latex(equation),
        "variable_solved": str(target) if target is not None else None,
        "is_identity": bool(identity), "is_contradiction": bool(contradiction),
    }
    solutions = [] if identity or contradiction else sp.solve(equation, target)
    solutions_latex: List[str] = []
    solutions_text: List[str] = []
    solutions_numeric: List[Optional[float]] = []
    for solution in solutions:
        simplified = sp.simplify(solution)
        solutions_latex.append(sp.latex(simplified))
        solutions_text.append(str(simplified))
        solutions_numeric.append(_safe_float(simplified))
    return {
        **base, "solutions_count": len(solutions),
        "solutions_latex": solutions_latex, "solutions_text": solutions_text,
        "solutions_numeric": solutions_numeric,
    }


def _evaluate_expression_worker(
    expression_str: str,
    precision: int,
    use_physics: bool = False,
    variables: Optional[Dict[str, Any]] = None,
    timeout_budget: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Core plain worker using an AST builder and exact numeric literals."""
    validate_input_length(expression_str)
    _validate_precision(precision)
    validated_variables = _validate_variables(variables)
    clean = sanitize_expression(expression_str)
    if not clean:
        raise ValueError("Expression is empty after sanitization.")
    try:
        parsed = _parse_plain_expression(clean)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in expression: {exc}") from exc
    evaluated = _evaluate_scalar(parsed, _active_substitutions(use_physics, validated_variables), timeout_budget)
    return {"status": "success", "input_expression": clean, **_scalar_result(evaluated, precision)}


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
    """Evaluate LaTeX within a deterministic timeout.

    precision must be 1--100. numeric_decimal is a string with that many
    significant digits; numeric_approximation is only a convenience float and
    retains decimal-place rounding for ordinary-sized values.
    """
    validate_input_length(latex_str)
    _validate_precision(precision)
    validated_variables = _validate_variables(variables)
    budget = clamp_timeout(timeout_seconds if timeout_seconds is not None else timeout)
    return run_with_timeout(
        _evaluate_latex_worker,
        args=(latex_str, precision, use_physics, validated_variables, budget),
        timeout_seconds=budget,
    )


def solve_equation(
    equation_str: str,
    variable: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Solve an equation with explicit is_identity / is_contradiction metadata."""
    validate_input_length(equation_str)
    if variable is not None:
        _validate_symbol_name(variable)
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
    """Evaluate plain scalar arithmetic without Python eval or string sympification.

    precision must be 1--100. numeric_decimal is a string with that many
    significant digits; numeric_approximation is only a convenience float and
    retains decimal-place rounding for ordinary-sized values.
    """
    validate_input_length(expression_str)
    _validate_precision(precision)
    validated_variables = _validate_variables(variables)
    budget = clamp_timeout(timeout_seconds if timeout_seconds is not None else timeout)
    return run_with_timeout(
        _evaluate_expression_worker,
        args=(expression_str, precision, use_physics, validated_variables, budget),
        timeout_seconds=budget,
    )
