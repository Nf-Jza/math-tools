"""Unit tests for the math sanitizer module."""

from math_tools.sanitizer import sanitize_expression, sanitize_latex


def test_sanitize_latex_delimiters():
    assert sanitize_latex(r"$$\frac{1}{2}$$") == r"\frac{1}{2}"
    assert sanitize_latex(r"$ \sqrt{16} $") == r"\sqrt{16}"
    assert sanitize_latex(r"\[ \int_0^1 x dx \]") == r"\int_0^1 x dx"
    assert sanitize_latex(r"\( 2 + 2 \)") == "2 + 2"


def test_sanitize_latex_markdown_blocks():
    raw = "```latex\n\\frac{3}{4}\n```"
    assert sanitize_latex(raw) == r"\frac{3}{4}"

    raw_math = "```math\n\\sqrt{9}\n```"
    assert sanitize_latex(raw_math) == r"\sqrt{9}"


def test_sanitize_latex_json_control_chars():
    # \x0c is form feed (\f) in unescaped JSON
    raw = "\x0crac{1}{2}"
    assert sanitize_latex(raw) == r"\frac{1}{2}"

    # \x08 is backspace (\b)
    raw_beta = "\x08eta + 1"
    assert sanitize_latex(raw_beta) == r"\beta + 1"

    # \x07 is bell (\a)
    raw_alpha = "\x07lpha"
    assert sanitize_latex(raw_alpha) == r"\alpha"


def test_sanitize_latex_trailing_punctuation():
    assert sanitize_latex(r"\frac{3}{4}.") == r"\frac{3}{4}"
    assert sanitize_latex(r"x + 5 = 10,") == "x + 5 = 10"


def test_sanitize_latex_unicode_operators():
    assert r"\times" in sanitize_latex("3 × 4")
    assert "/" in sanitize_latex("10 ÷ 2")
    assert "-" in sanitize_latex("5 − 3")  # Unicode minus


def test_sanitize_expression():
    assert sanitize_expression("15% of 850") == "((15 / 100) * 850)"
    assert sanitize_expression("25%") == "(25 / 100)"
    assert sanitize_expression("2^8") == "2**8"
    assert sanitize_expression("10 x 5") == "10 * 5"
    assert sanitize_expression("12 * 4.") == "12 * 4"
