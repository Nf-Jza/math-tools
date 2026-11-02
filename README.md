# 🧮 Math-Tools MCP: Deterministic LLM Math & Symbolic Engine

> **Mission:** Reduce arithmetic and symbolic-computation errors by delegating calculations to a deterministic SymPy backend. Correct results still depend on the supplied formula, parsing, assumptions, and reference data; deterministic execution is not a proof of end-to-end correctness.

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
LLM -> Reports the computed result and checks its interpretation
```

---

## 🚀 Quickstart & Installation

`math-tools` runs directly from GitHub via [`uv`](https://docs.astral.sh/uv/) without needing manual git clones or path configuration.

### ⚡ 1-Command Installation for AI Agents & CLIs

#### Claude Code CLI:
```bash
claude mcp add math-tools -- uvx --from git+https://github.com/Nf-Jza/math-tools.git math-tools
```

#### Hermes Agent:
```bash
hermes mcp add math-tools uvx --from git+https://github.com/Nf-Jza/math-tools.git math-tools
```

---

### ⚙️ Direct MCP JSON Configuration

Clients such as **Claude Desktop**, **Claude Code**, **Cursor**, **Windsurf**, and **VS Code** can launch the stdio server. The following is an `mcpServers`-style configuration; adapt its wrapper to your client's schema:

```json
{
  "mcpServers": {
    "math-tools": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Nf-Jza/math-tools.git",
        "math-tools"
      ]
    }
  }
}
```

*Config file locations:*
- **Claude Desktop:** `~/.config/Claude-3p/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows)
- **Claude Code CLI:** Prefer `claude mcp add` above; use a project-root `.mcp.json` for shared project configuration.
- **Other clients:** Use the client's MCP settings UI or documented configuration file; locations differ between Cursor, Windsurf, and VS Code.

---

### 🛠️ Local Development & Manual Installation

For local development or testing modifications:

```bash
git clone https://github.com/Nf-Jza/math-tools.git
cd math-tools
uv sync
uv run pytest
```

Local MCP configuration (on Windows, use the executable at `.venv\\Scripts\\math-tools.exe` instead):
```json
{
  "mcpServers": {
    "math-tools": {
      "command": "/absolute/path/to/math-tools/.venv/bin/math-tools"
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
  * `precision` (`integer`, optional, default `10`, range `1`–`100`): Significant digits for `numeric_decimal`. The convenience float keeps legacy decimal-place rounding at ordinary magnitudes and significant digits for very small values.
  * `use_physics` (`boolean`, optional, default `false`): When `true`, automatically substitutes universal physical constants ($c, \hbar, G, k_B, \alpha, \varepsilon_0, \mu_0, m_e, m_p$).
  * `variables` (`object`, optional): Up to 64 public ASCII names mapped to finite real numbers or bounded decimal/scientific/rational literals (e.g. `{"m": 0.001}`, `{"x": "1/3"}`). Names cannot shadow mathematical functions or constants; symbolic code strings are rejected.
  * `timeout_seconds` (`number`, optional, default `5.0`): Execution timeout budget in seconds (min `0.1`, max `30.0`).
* **Example Response:**
  ```json
  {
    "status": "success",
    "exact_latex": "\\frac{62838}{7}",
    "exact_text": "62838/7",
    "numeric_approximation": 8976.8571428571,
    "is_rational": true
  }
  ```

### 2. `evaluate_expression`
Evaluates standard non-LaTeX arithmetic, percentages, scientific notation, and algebraic expressions safely.
* **Arguments:**
  * `expression` (`string`, required): Arithmetic expression (e.g. `15% of 850`, `sqrt(256) + 2^5`, `(453 * 12) / (7 + 3)`).
  * `precision` (`integer`, optional, default `10`, range `1`–`100`): Significant digits for `numeric_decimal`; `numeric_approximation` remains a machine-precision convenience float.
  * `use_physics` (`boolean`, optional, default `false`): Enables physical constant substitution.
  * `variables` (`object`, optional): Same validated finite-numeric mapping as `evaluate_latex`; symbolic expression strings are not accepted.
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

**Numeric output contract:** `numeric_approximation` is a JSON number, so it is limited to machine-float range and precision. `numeric_decimal` is a significant-digit decimal/scientific string evaluated by SymPy; use it for high precision, very small values, or values beyond the float range. Either may be `null` when no finite real approximation is available. Exact rational and symbolic text is retained separately. Decimal literals in plain expressions are interpreted exactly; JSON floating-point substitutions have already been rounded by the client and cannot regain lost precision.

Matrix results use JSON-safe `matrix_data`: small exact integers are JSON numbers, while rational, symbolic, and large-integer cells are strings. This avoids silently converting exact fractions to floats. `determinant` and `trace` are convenience floats when finite and real.

### 3. `solve_equation`
Finds exact symbolic and numerical roots of algebraic equations and polynomials. Identity/constant-equation responses distinguish `is_identity` from `is_contradiction`; an identity's empty root list does not mean that no values satisfy it.
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
        └── k_B (Boltzmann)      └── ε_0, μ_0 (Vacuum)
```

1. **Exact SI 2019 Constants ($c, h, \hbar, k_B, e, N_A$):**
   * Defining SI values, or exact mathematical relations derived from them (such as $\hbar = h/(2\pi)$), under the current SI definitions. They have **zero definitional uncertainty**; the implementation still requires accurate transcription and regression tests.
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
│  │    - Mathematical input normalization           │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ Clean Token String         │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ 2. Guardrails & Safety Boundary                  │  │
│  │    - forkserver / Windows spawn workers         │  │
│  │    - Configurable execution timeout (default 5s) │  │
│  │    - Explicit plain-expression AST evaluation   │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ AST Tree                   │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ 3. Computation Engine (SymPy + ANTLR)            │  │
│  │    - Exact Rational fractions (\frac{a}{b})      │  │
│  │    - Numerical evaluation via SymPy/mpmath      │  │
│  │    - Symbolic simplification & equation solving  │  │
│  │    - Physical constants registry                 │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 🛡️ Built-in Safety & Security

* **Explicit mathematical parsing:** Plain expressions and equation fallbacks use a whitelisted AST evaluator. Variable substitutions are restricted to validated finite numeric values; arbitrary Python strings are not evaluated as substitution code. LaTeX uses strict parser backends rather than silently accepting an incomplete prefix.
* **Worker circuit breaker:** Computations run in a separate process (`forkserver` where supported, `spawn` on Windows) with a bounded response wait. Results are drained over a one-way pipe while the worker is running, before joining it. Startup and cleanup add overhead; this is not a real-time scheduling guarantee.
* **Not an OS sandbox:** Workers retain the server account's privileges. No filesystem/network isolation or memory quota is provided. Use an OS-level sandbox and a least-privilege account for untrusted workloads; timeouts do not bound peak memory allocation.
* **LaTeX control-character repair:** Common incorrectly escaped LaTeX control characters are repaired. Normalization preserves factorial operators; malformed or unsupported syntax is rejected rather than guaranteed to be repairable.
* **Result representations:** Scalar responses preserve the symbolic expression and provide a machine-float approximation when available. Numerical evaluation is approximate, and exact-looking text containing measured constants is not an exact physical measurement. Boolean, equation, and matrix results have their own response fields.
* **Physics scope:** The catalog supplies SI values and CODATA reference metadata. Units are labels, not dimensional constraints, and measurement uncertainties are not propagated through formulas.

---

## 🧪 Testing

Run the full unit, integration, security-rejection, and regression suite:

```bash
uv run pytest
```

CI runs the locked environment on Windows and Ubuntu with Python 3.12, 3.13, and 3.14. Successful local tests do not establish that every symbolic expression will terminate or that every physical formula is valid.
