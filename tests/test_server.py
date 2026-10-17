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
