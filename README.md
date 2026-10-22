# 🧮 Math-Tools MCP: Deterministic LLM Math & Symbolic Engine

> **Mission:** Completely eliminate Large Language Model mathematical hallucinations by shifting the agent from statistical token prediction to **guaranteed deterministic computation**.

---

## 🎯 The Core Problem & Solution

```
❌ The Hallucination Loop (Pure LLM):
User: "What is \frac{3491 \times 18}{7}?"
LLM Internal Prediction: "8976.85..." (Token guessing -> Plausible-looking fiction)

✅ Deterministic Tool-Use (Math-Tools MCP):
User: "What is \frac{3491 \times 18}{7}?"
LLM -> Calls evaluate_latex(latex="\frac{3491 \times 18}{7}")
Engine -> SymPy / ANTLR AST deterministic evaluation
Engine -> Returns Exact: 62838/7 | Numeric: 8976.857142857143
LLM -> Answers strictly with certified computed output
```

---

## 🏗️ Architectural Overview

```
┌────────────────────────────────────────────────────────┐
│                   AI Agent Client                      │
│            (Hermes / Claude Code / Cursor)             │
└───────────────────────────┬────────────────────────────┘
                            │ JSON-RPC over Stdio (MCP)
┌───────────────────────────▼────────────────────────────┐
│                  Math-Tools MCP Server                 │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1. Sanitization & Escaping Gate                  │  │
│  │    - Strip $ / $$ math delimiters                │  │
│  │    - Auto-heal single-escaped backslashes        │  │
│  │    - Strict regex input pre-validation           │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ Clean Token String         │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ 2. Guardrails & Safety Boundary                  │  │
│  │    - 5.0s hard execution timeout                 │  │
│  │    - Zero eval() / exec() -> pure SymPy AST      │  │
│  │    - Memory consumption limits                   │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ AST Tree                   │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ 3. Computation Engine (SymPy + ANTLR)            │  │
│  │    - Exact Rational fractions (\frac{a}{b})      │  │
│  │    - High-precision floating points (evalf)      │  │
│  │    - Symbolic simplification & equation solving  │  │
│  │    - Calculus (derivatives, integrals, limits)   │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ MCP Tool Definitions

### 1. `evaluate_latex`
* **Purpose:** Evaluates raw LaTeX mathematical expressions directly.
* **Input Parameters:**
  * `latex` (`string`, required): LaTeX formula (e.g. `\frac{3}{4} + \sqrt{144}`, `\int_0^\pi \sin(x)dx`).
  * `precision` (`integer`, optional, default `10`): Number of decimal digits for floating-point approximation.
* **Response Payload:**
  ```json
  {
    "status": "success",
    "exact_latex": "\\frac{51}{4}",
    "exact_text": "51/4",
    "numeric_approximation": 12.75,
    "is_exact_integer_or_rational": true
  }
  ```

### 2. `solve_equation`
* **Purpose:** Solves algebraic equations or systems of equations deterministically.
* **Input Parameters:**
  * `equation` (`string`, required): Standard or LaTeX equation (e.g. `2*x + 5 = 15` or `x^2 - 4 = 0`).
  * `variable` (`string`, optional, default `"x"`): Target variable to solve for.
* **Response Payload:**
  ```json
  {
    "status": "success",
    "solutions_latex": ["-2", "2"],
    "solutions_numeric": [-2.0, 2.0]
  }
  ```

### 3. `evaluate_expression`
* **Purpose:** Evaluates standard arithmetic, scientific notation, percentages, and algebraic expressions without LaTeX notation.
* **Input Parameters:**
  * `expression` (`string`, required): Arithmetic expression (e.g. `15% of 850`, `(453 * 12) / (7 + 3)`, `sqrt(256) + 2^5`).
* **Response Payload:**
  ```json
  {
    "status": "success",
    "exact_result": "2718/5",
    "numeric_result": 543.6
  }
  ```

---

## 🛡️ Safety & Reliability Principles

1. **Deterministic Sandboxing:** Absolutely no raw `eval()` or dynamic string code execution. All calculations occur via abstract syntax trees (SymPy / ANTLR parser).
2. **Double-Backslash Resilience:** LLMs commonly drop backslashes in JSON (e.g., transmitting `\frac` as `\x0c` or raw `frac`). The ingestion gate automatically repairs and sanitizes LaTeX escape sequences.
3. **Execution Circuit Breaker:** Any symbolic operation (such as indefinite symbolic integration or high-degree factoring) that exceeds 5.0 seconds is immediately aborted with a timeout response.
4. **Structured Dual Output:** Always return both the **exact rational/symbolic form** (e.g., `19/4`) and the **decimal approximation** (e.g., `4.75`) so the LLM can present whichever matches user intent.
