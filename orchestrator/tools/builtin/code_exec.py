"""Python code execution tool (subprocess-isolated)."""

import asyncio
import os
import tempfile
from typing import Any

from orchestrator.tools.base import BaseTool, ToolParam


class CodeExecTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="code_exec",
            description="Execute Python code and return stdout/stderr. Use for calculations, data processing, testing ideas.",
            parameters=[
                ToolParam(name="code", type="string", description="Python code to execute"),
            ],
        )

    async def execute(self, code: str, **kwargs: Any) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                return "[code_exec] Error: execution timed out (30s)"

            output = stdout.decode()[:3000]
            errors = stderr.decode()[:1000]
            result = f"[code_exec] Exit code: {proc.returncode}\n"
            if output:
                result += f"stdout:\n{output}\n"
            if errors:
                result += f"stderr:\n{errors}\n"
            return result
        finally:
            os.unlink(tmp_path)
