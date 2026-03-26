"""Base class for all executable tools."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class ToolParam(BaseModel):
    """Single parameter for a tool."""
    name: str
    type: str  # "string", "number", "boolean"
    description: str
    required: bool = True


class BaseTool(ABC):
    """Abstract base for executable tools."""

    name: str
    description: str
    parameters: list[ToolParam]

    def __init__(self, name: str, description: str, parameters: list[ToolParam] | None = None):
        self.name = name
        self.description = description
        self.parameters = parameters or []

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function_calling schema for the router."""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return result as string."""
        ...
