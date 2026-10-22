# 🧮 Math-Tools MCP: Deterministic LLM Math & Symbolic Engine

> **Mission:** Completely eliminate Large Language Model mathematical hallucinations by shifting the agent from statistical token prediction to **guaranteed deterministic computation**.

---

## 🎯 Core Operating Principle

**Never calculate in your head.** Large Language Models are statistical next-token prediction engines, not calculators. Whenever a prompt involves:
- Arithmetic, fractions, or percentages
- Calculus (derivatives, integrals, limits)
- Matrix algebra or determinants
- Algebraic equations (roots, polynomials)
- Universal physical constants ($c, \hbar, G, k_B, \alpha$)

**Delegate immediately to `math-tools` via MCP.**

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

## 🚀 Quickstart & MCP Configuration

### 1. Installation

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/Nf-Jza/math-tools.git
cd math-tools
uv sync
```

### 2. Registering in MCP Clients

#### Claude Desktop (`~/.config/Claude-3p/claude_desktop_config.json` or `~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "math-tools": {
      "command": "/path/to/math-tools/.venv/bin/math-tools"
    }
  }
}
```

#### Claude Code CLI (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "math-tools": {
      "command": "/path/to/math-tools/.venv/bin/math-tools"
    }
  }
}
```

#### Hermes / Cursor (`mcp.json`):
```json
{
  "mcpServers": {
    "math-tools": {
      "command": "/path/to/math-tools/.venv/bin/math-tools"
    }
  }
}
```

---

## 🛠️ MCP Tool Reference

### 1. `evaluate_latex`
Evaluates raw LaTeX equations, integrals, derivatives, limits, summations, and matrix expressions.
* **Arguments:**
  * `latex` (`string`, required): Raw LaTeX formula (e.g. `\frac{3491 \times 18}{7}`, `\int_0^\pi \sin(x)dx`, `\det \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}`).
  * `precision` (`integer`, optional, default `10`): Decimal digits for floating-point approximation.
  * `use_physics` (`boolean`, optional, default `false`): When `true`, automatically substitutes universal physical constants ($c, \hbar, G, k_B, \alpha, \varepsilon_0, \mu_0, m_e, m_p$).
  * `variables` (`object`, optional): Key-value mappings for free variables (e.g. `{"m": 0.001}`).
  * `timeout_seconds` (`number`, optional, default `5.0`): Execution timeout budget in seconds (min `0.1`, max `30.0`).
* **Example Response:**
  ```json
  {
    "status": "success",
    "exact_latex": "\\frac{62838}{7}",
    "exact_text": "62838/7",
    "numeric_approximation": 8976.857142857143,
    "is_exact_integer_or_rational": true
  }
  ```

### 2. `evaluate_expression`
Evaluates standard non-LaTeX arithmetic, percentages, scientific notation, and algebraic expressions safely.
* **Arguments:**
  * `expression` (`string`, required): Arithmetic expression (e.g. `15% of 850`, `sqrt(256) + 2^5`, `(453 * 12) / (7 + 3)`).
  * `precision` (`integer`, optional, default `10`): Decimal digits for float approximation.
  * `use_physics` (`boolean`, optional, default `false`): Enables physical constant substitution.
  * `variables` (`object`, optional): Key-value mappings for free variables.
  * `timeout_seconds` (`number`, optional, default `5.0`).
* **Example Response:**
  ```json
  {
    "status": "success",
    "exact_text": "2718/5",
    "numeric_approximation": 543.6,
    "is_number": true
  }
  ```

### 3. `solve_equation`
Finds exact symbolic and numerical roots of algebraic equations and polynomials.
* **Arguments:**
  * `equation` (`string`, required): Algebraic equation or LaTeX equation (e.g. `2x + 5 = 15`, `x^2 - 5x + 6 = 0`, `\frac{x}{3} = 4`).
  * `variable` (`string`, optional): Target variable to isolate (e.g. `"x"`). Defaults to primary symbol.
  * `timeout_seconds` (`number`, optional, default `5.0`).
* **Example Response:**
  ```json
  {
    "status": "success",
    "equation_latex": "x^{2} - 5 x + 6 = 0",
    "variable_solved": "x",
    "solutions_count": 2,
    "solutions_latex": ["2", "3"],
    "solutions_numeric": [2.0, 3.0]
  }
  ```

### 4. `get_physics_constant`
Queries exact definitions, numerical values, SI units, and authoritative CODATA/BIPM citations for universal constants.
* **Arguments:**
  * `symbol` (`string`, required): Constant identifier (e.g. `"c"`, `"hbar"`, `"h"`, `"G"`, `"k_B"`, `"alpha"`, `"eps_0"`, `"mu_0"`, `"m_e"`, `"m_p"`, `"N_A"`, `"R_gas"`).
* **Example Response:**
  ```json
  {
    "status": "success",
    "symbol": "c",
    "name": "Speed of Causality / Light in Vacuum",
    "exact_value_text": "299792458",
    "numeric_value": 299792458.0,
    "unit": "m/s",
    "category": "EXACT_SI",
    "source": "BIPM SI Brochure (9th Edition)"
  }
  ```

---

## 🔬 Scientific Constant Epistemology & Agent Healthcheck Protocol

Science progresses continuously. To prevent codebase drift without adding fragile scraping dependencies to the Python backend, the AI agent acts as the scientific auditor.

### Constant Classification

```
┌────────────────────────────────────────────────────────┐
│                   Universal Constants                  │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       [Fixed by SI 2019]       [Empirical / CODATA]
       Exact by definition      Periodic re-measurement
       (Zero uncertainty)       (Subject to scientific updates)
        ├── c (Speed of light)   ├── G (Gravitational constant)
        ├── h, ℏ (Planck)        ├── α (Fine-structure constant)
        ├── e (Elementary charge)├── m_e, m_p (Particle masses)
        └── k_B (Boltzmann)      └── H_0, Λ (Cosmology)
```

1. **Exact SI 2019 Constants ($c, h, \hbar, k_B, e, N_A$):**
   * Mathematically fixed by international treaty (BIPM 9th Edition). They have **zero uncertainty** and will never change.
2. **Empirical CODATA Constants ($G, \alpha, \varepsilon_0, \mu_0, m_e, m_p$):**
   * Experimentally determined physical constants. Periodically updated by CODATA (Committee on Data for Science and Technology) and NIST.

### 🌐 Agent Verification Workflow

When an agent is asked to perform mission-critical physical computations or an audit:
1. **Do not modify inline Python code with automated scrapers.**
2. **Consult authoritative scientific repositories:**
   * **NIST Fundamental Physical Constants:** `https://physics.nist.gov/cuu/Constants/`
   * **BIPM International Bureau of Weights and Measures:** `https://www.bipm.org/en/measurement-units/si-base-units`
   * **Particle Data Group (PDG):** `https://pdg.lbl.gov`
3. **Notify and Propose Updates:** If new CODATA adjustments or experimental values differ from `src/math_tools/physics.py`:
   * Clearly state the newly published value, uncertainty interval, and publication date.
   * Provide the user with the proposed diff for `src/math_tools/physics.py`.
   * Request user confirmation before applying updates.

---

## 🏗️ Architecture & Internal Pipeline

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
│  │    - Subprocess forkserver isolation             │  │
│  │    - Configurable execution timeout (default 5s) │  │
│  │    - Zero eval() / exec() -> pure AST whitelist  │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ AST Tree                   │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ 3. Computation Engine (SymPy + ANTLR)            │  │
│  │    - Exact Rational fractions (\frac{a}{b})      │  │
│  │    - Numerical quadrature fallback (scipy/mpmath)│  │
│  │    - Symbolic simplification & equation solving  │  │
│  │    - Physical constants engine                   │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 🛡️ Built-in Safety & Security

* **Zero `eval()` / Zero `exec()`:** Standard expressions pass through Python's Abstract Syntax Tree (`ast.parse`) validation whitelist. Any disallowed node (`Import`, `Attribute`, `Lambda`) or unauthorized function call is rejected before evaluation.
* **Process Isolation & Circuit Breaker:** All computations run inside an isolated subprocess via Python's forkserver model. Combinatorial explosions or runaway recursions are terminated cleanly at the timeout boundary.
* **LaTeX Control Character Auto-Repair:** JSON unescaped backslashes (`\x0c` formfeed $\to$ `\f`, `\x08` $\to$ `\b`, `\x0b` $\to$ `\v`) are repaired automatically.
* **Structured Dual Output:** Always returns both the exact rational/symbolic form and high-precision numeric decimal approximation.

---

## 🧪 Testing

Run the full test suite (49 unit, integration, and security stress tests):

```bash
uv run pytest
```
