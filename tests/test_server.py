"""Unit tests for the MCP server interface."""

import json
import pytest
from math_tools.server import server


@pytest.mark.anyio
async def test_server_list_tools():
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "evaluate_latex" in tool_names
    assert "evaluate_expression" in tool_names
    assert "solve_equation" in tool_names
    assert "get_physics_constant" in tool_names


@pytest.mark.anyio
async def test_server_call_evaluate_latex():
    res = await server.call_tool("evaluate_latex", {"latex": r"\frac{3}{4} + \sqrt{16}"})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["numeric_approximation"] == 4.75


@pytest.mark.anyio
async def test_server_call_evaluate_expression():
    res = await server.call_tool("evaluate_expression", {"expression": "15% of 850"})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["numeric_approximation"] == 127.5


@pytest.mark.anyio
async def test_server_call_solve_equation():
    res = await server.call_tool("solve_equation", {"equation": "2x + 5 = 15"})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["solutions_numeric"] == [5.0]


@pytest.mark.anyio
async def test_server_call_get_physics_constant():
    res = await server.call_tool("get_physics_constant", {"symbol": "c"})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["numeric_value"] == 299792458.0
    assert data["unit"] == "m/s"


@pytest.mark.anyio
async def test_server_call_timeout_seconds():
    res = await server.call_tool(
        "evaluate_latex",
        {
            "latex": r"\int_{1}^{2} \frac{x^2-2}{(x^2+2) \sqrt{x^4+4}} \, dx",
            "timeout_seconds": 10.0,
        },
    )
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert abs(data["numeric_approximation"]) < 1e-6


@pytest.mark.anyio
async def test_server_call_matrix_is_json_safe():
    res = await server.call_tool(
        "evaluate_latex",
        {"latex": r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}"},
    )
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["type"] == "matrix"
    assert data["matrix_data"] == [[1, 2], [3, 4]]
    assert data["determinant"] == -2.0


@pytest.mark.anyio
async def test_server_rejects_symbolic_substitution_strings():
    res = await server.call_tool(
        "evaluate_expression", {"expression": "x + 1", "variables": {"x": "sin(1)"}}
    )
    data = json.loads(res.content[0].text)
    assert data["status"] == "error"
    assert data["error_type"] in {"TypeError", "ValueError"}


@pytest.mark.anyio
async def test_server_preserves_small_scientific_values():
    res = await server.call_tool(
        "evaluate_expression", {"expression": "q_e", "use_physics": True}
    )
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["numeric_approximation"] == pytest.approx(1.602176634e-19, rel=1e-9, abs=0)
    assert isinstance(data["numeric_decimal"], str)


@pytest.mark.anyio
async def test_server_preserves_terminal_factorial():
    res = await server.call_tool("evaluate_latex", {"latex": "5!"})
    data = json.loads(res.content[0].text)
    assert data["status"] == "success"
    assert data["exact_text"] == "120"

