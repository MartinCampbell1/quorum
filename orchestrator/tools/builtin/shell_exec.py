"""Shell command execution tool."""

import asyncio
from typing import Any

from orchestrator.tools.base import BaseTool, ToolParam


class ShellExecTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="shell_exec",
            description="Execute shell commands. Use for system operations, file management, git commands.",
            parameters=[
                ToolParam(name="command", type="string", description="Shell command to execute"),
                ToolParam(name="workdir", type="string", description="Working directory", required=False),
            ],
        )

    async def execute(self, command: str, workdir: str = "/tmp", **kwargs: Any) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                return f"[shell] Error: timeout (30s) for: {command}"

            output = stdout.decode()[:3000]
            errors = stderr.decode()[:1000]
            result = f"[shell] $ {command}\nExit: {proc.returncode}\n"
            if output:
                result += output + "\n"
            if errors:
                result += f"stderr: {errors}\n"
            return result
        except Exception as e:
            return f"[shell] Error: {e}"
