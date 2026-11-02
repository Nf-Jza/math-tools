"""Exercise the installed entry point over a real MCP stdio connection."""

import json
from pathlib import Path
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.mark.anyio
async def test_stdio_initialize_list_and_calculate():
    executable = Path(sys.executable).with_name(
        "math-tools.exe" if sys.platform == "win32" else "math-tools"
    )
    parameters = StdioServerParameters(command=str(executable))
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=20.0) as session:
            initialized = await session.initialize()
            assert initialized.server_info.name == "math-tools"
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "evaluate_expression", "evaluate_latex", "solve_equation", "get_physics_constant"
            }
            result = await session.call_tool(
                "evaluate_expression", {"expression": "15% of 850"}
            )
            assert not result.is_error
            data = json.loads(result.content[0].text)
            assert data["status"] == "success"
            assert data["exact_text"] == "255/2"
            assert data["numeric_approximation"] == 127.5

            matrix = await session.call_tool(
                "evaluate_latex",
                {"latex": r"\begin{pmatrix} \frac{1}{3} & x \\ 3 & 4 \end{pmatrix}",
                 "variables": {"x": 2}},
            )
            matrix_data = json.loads(matrix.content[0].text)
            assert matrix_data["status"] == "success"
            assert matrix_data["matrix_data"] == [["1/3", 2], [3, 4]]

            invalid = await session.call_tool(
                "evaluate_expression", {"expression": "x", "variables": {"x": "sin(1)"}}
            )
            assert json.loads(invalid.content[0].text)["status"] == "error"

            # A rejected call must not break the session or subsequent workers.
            recovered = await session.call_tool("evaluate_latex", {"latex": "5!"})
            assert json.loads(recovered.content[0].text)["exact_text"] == "120"
