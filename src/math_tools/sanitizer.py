"""Sanitization and input normalization layer for mathematical expressions."""

import re

# Mapping of common unicode characters to clean LaTeX / ASCII representations
UNICODE_MATH_MAP = {
    "\u00d7": r" \times ",  # ×
    "\u00f7": " / ",        # ÷
    "\u2212": "-",          # − (Unicode minus)
    "\u00b7": r" \cdot ",   # · (middle dot)
    "\u2022": r" \cdot ",   # • (bullet dot)
    "\u03c0": r" \pi ",     # π
    "\u221e": r" \infty ",  # ∞
    "\u2264": r" \le ",     # ≤
    "\u2265": r" \ge ",     # ≥
    "\u2260": r" \ne ",     # ≠
    "\u221a": r" \sqrt ",   # √
}


def sanitize_latex(raw_input: str) -> str:
    """Sanitize and repair LaTeX math input from LLMs.

    Handles:
    - Control characters (\\x0c, \\x0b, \\x08, \\x07, \\t) repaired before stripping
    - Code fences (```latex, ```math, ```)
    - Delimiters ($$, $, \\[ \\], \\( \\))
    - LaTeX environment wrappers (equation, align*, gather*)
    - Display style macros (\\displaystyle, \\textstyle)
    - Differential notation (\\mathrm{d}x -> d x)
    - Trailing punctuation (sentences ending with '.')
    - Unicode mathematical symbols
    """
    if not raw_input or not isinstance(raw_input, str):
        return ""

    text = raw_input

    # 1. Repair unescaped JSON control characters BEFORE any whitespace stripping
    text = text.replace("\x0c", r"\f")
    text = text.replace("\x0b", r"\v")
    text = text.replace("\x08", r"\b")
    text = text.replace("\x07", r"\a")
    text = re.sub(r"\t(imes|ext|heta|an|o|au|riangle)", r"\\t\1", text)

    # 2. Strip leading/trailing space and newlines
    text = text.strip()

    # 3. Strip markdown fences
    text = re.sub(r"^```(?:latex|math|[a-zA-Z0-9_-]+)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?\s*```$", "", text)
    text = text.strip()

    # 4. Strip display / inline math wrappers
    if text.startswith("$$") and text.endswith("$$") and len(text) >= 4:
        text = text[2:-2].strip()
    elif text.startswith("$") and text.endswith("$") and len(text) >= 2:
        text = text[1:-1].strip()
    elif text.startswith(r"\[") and text.endswith(r"\]") and len(text) >= 4:
        text = text[2:-2].strip()
    elif text.startswith(r"\(") and text.endswith(r"\)") and len(text) >= 4:
        text = text[2:-2].strip()

    # 5. Strip outer environment wrappers if wrapped in single equation/align block
    env_pattern = r"^\\begin\{(?:equation\*?|align\*?|gather\*?|displaymath)\}([\s\S]*)\\end\{(?:equation\*?|align\*?|gather\*?|displaymath)\}$"
    env_match = re.match(env_pattern, text)
    if env_match:
        text = env_match.group(1).strip()

    # 6. Strip font/style sizing macros that LLMs frequently output
    text = re.sub(r"\\(?:displaystyle|textstyle|scriptstyle|scriptscriptstyle)\s*", "", text)

    # 7. Normalize differential notation: \mathrm{d}x, \text{d}x -> d x
    text = re.sub(r"\\(?:mathrm|text)\s*\{\s*d\s*\}\s*([a-zA-Z])", r"d \1", text)

    # 8. Unicode character replacement
    for uni_char, replacement in UNICODE_MATH_MAP.items():
        text = text.replace(uni_char, replacement)

    # 9. Trailing punctuation removal
    text = re.sub(r"([)}\]\w\\])[.,;?!]+$", r"\1", text)

    return text.strip()


def sanitize_expression(raw_input: str) -> str:
    """Sanitize general non-LaTeX expressions.

    Handles:
    - Code fences
    - Common percentage syntax ('15% of 850' -> '(15 / 100) * 850')
    - 'x' / '×' as multiplication between numbers
    - Exponentiation symbol '^' -> '**'
    - Unicode symbols
    """
    if not raw_input or not isinstance(raw_input, str):
        return ""

    text = raw_input.strip()

    # 1. Strip markdown fences
    text = re.sub(r"^```(?:python|math|[a-zA-Z0-9_-]+)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?\s*```$", "", text)
    text = text.strip()

    # 2. Percentage conversions: e.g. "15% of 850" -> "(15 / 100) * 850"
    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*%\s+of\s+([a-zA-Z0-9_.()]+)",
        r"((\1 / 100) * \2)",
        text,
        flags=re.IGNORECASE,
    )

    # Trailing percentages: e.g. "25%" -> "(25 / 100)"
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1 / 100)", text)

    # 3. Unicode replacements
    for uni_char, replacement in UNICODE_MATH_MAP.items():
        text = text.replace(uni_char, replacement)

    # 4. Caret exponentiation -> Python exponentiation
    text = text.replace("^", "**")

    # 5. Multiply symbol cleanup: '2 * 3' or '2 x 3' -> '2 * 3'
    text = re.sub(r"(\d+)\s*[xX]\s*(\d+)", r"\1 * \2", text)

    # 6. Trailing punctuation
    text = re.sub(r"([)}\]\w])[.,;?!]+$", r"\1", text)

    return text.strip()
