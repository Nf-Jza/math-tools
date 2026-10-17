# 📖 How-To Guide: Math-Tools MCP & Agent Operational Protocol

> **Purpose:** Operational manual for AI agents (Hermes, Claude Code, Cursor) to reliably perform deterministic mathematical and physical computations, and protocol for maintaining scientific currency.

---

## 🎯 Core Operating Principle

**Never calculate in your head.** Large Language Models are statistical next-token prediction engines, not calculators. Whenever a prompt involves:
- Arithmetic, fractions, or percentages
- Calculus (derivatives, integrals, limits)
- Matrix algebra or determinants
- Algebraic equations (roots, polynomials)
- Universal physical constants ($c, \hbar, G, k_B, \alpha$)

**Delegate immediately to `math-tools` via MCP.**

---

## 🛠️ MCP Tool Interface

### 1. `evaluate_latex`
Evaluates raw LaTeX equations and mathematical expressions.
* **Arguments:**
  * `latex` (`string`, required): The LaTeX math string (e.g. `\frac{3491 \times 18}{7}`, `\int_0^\pi \sin(x)dx`, `\det \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}`).
  * `precision` (`integer`, optional, default `10`): Decimal digits for float approximation.
  * `use_physics` (`boolean`, optional, default `false`): When `true`, substitutes universal physical constants ($c, \hbar, G, k_B, \alpha, \varepsilon_0, \mu_0, m_e, m_p$).
  * `variables` (`object`, optional): Key-value mappings for free variables (e.g. `{"m": 0.001}`).

### 2. `evaluate_expression`
Evaluates standard non-LaTeX expressions, percentages, and scientific notation safely.
* **Arguments:**
  * `expression` (`string`, required): Arithmetic expression (e.g. `15% of 850`, `sqrt(256) + 2^5`, `(453 * 12) / (7 + 3)`).
  * `precision` (`integer`, optional, default `10`).
  * `use_physics` (`boolean`, optional, default `false`).
  * `variables` (`object`, optional).

### 3. `solve_equation`
Finds exact and numerical roots of algebraic equations.
* **Arguments:**
  * `equation` (`string`, required): Equation string (e.g. `2x + 5 = 15`, `x^2 - 5x + 6 = 0`, `\frac{x}{3} = 4`).
  * `variable` (`string`, optional): Target variable to isolate (e.g. `"x"`). Defaults to the primary symbol.

### 4. `get_physics_constant`
Queries exact metadata, units, and definitions of physical constants.
* **Arguments:**
  * `symbol` (`string`, required): Symbol name (e.g. `"c"`, `"hbar"`, `"G"`, `"k_B"`, `"alpha"`, `"eps_0"`, `"mu_0"`, `"m_e"`, `"m_p"`).

---

## 🔬 Scientific Constant Epistemology & Agent Healthcheck Protocol

Science progresses continuously. To prevent codebase drift without adding fragile scraping dependencies to the Python backend, the AI agent itself acts as the scientific auditor.

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

1. **Exact SI 2019 Constants ($c, h, \hbar, k_B, q_e, N_A$):**
   * These are mathematically fixed by international treaty (BIPM 9th Edition). They have **zero uncertainty** and will never change.
2. **Empirical CODATA Constants ($G, \alpha, \varepsilon_0, \mu_0, m_e, m_p$):**
   * These are experimentally determined physical constants. Every 4 years, CODATA (Committee on Data for Science and Technology) and NIST publish updated recommended values.

---

### 🌐 Agent Verification Workflow (Finding Trusted Sources)

When an agent is asked to perform mission-critical physical computations, or when asked to perform a scientific audit / healthcheck:

1. **Do not modify inline Python code with automated scrapers.**
2. **Use external agent tools:** Use web search (`mcp__websearch-mcp__search` or DuckDuckGo) to check the latest measurements against authoritative scientific repositories:
   * **NIST Fundamental Physical Constants:** `https://physics.nist.gov/cuu/Constants/`
   * **BIPM International Bureau of Weights and Measures:** `https://www.bipm.org/en/measurement-units/si-base-units`
   * **Particle Data Group (PDG):** `https://pdg.lbl.gov`
3. **Notify and Propose Updates:** If new CODATA adjustments or experimental values are officially confirmed that differ from `src/math_tools/physics.py`:
   * Clearly state the newly published value, the uncertainty interval, and the publication date.
   * Provide the user with the proposed diff for `src/math_tools/physics.py`.
   * Ask the user for explicit confirmation before updating the catalog.

---

## 🛡️ Built-in Safety & Security

* **Zero `eval()` / Zero `exec()`:** Standard expressions pass through Python's Abstract Syntax Tree (`ast.parse`) validation whitelist. Any disallowed node (`Import`, `Attribute`, `Lambda`) or unauthorized function call is rejected before evaluation.
* **5.0s Process Isolation:** All calculations execute in a spawned subprocess. If an expression causes a combinatorial explosion or infinite recursion, the process is terminated within 5.0 seconds.
* **LaTeX Control Character Auto-Repair:** JSON unescaped backslashes (`\x0c` formfeed $\to$ `\f`, `\x08` $\to$ `\b`, `\x0b` $\to$ `\v`) are repaired automatically.
