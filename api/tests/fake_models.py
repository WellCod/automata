"""Modelos falsos para testes de runtime: chamam uma tool e depois respondem."""

import json
from dataclasses import dataclass
from typing import Any

from agno.models.response import ModelResponse

from app.agents.replay import ReplayModel


@dataclass
class ToolCallingModel(ReplayModel):
    """Na primeira volta pede `tool_name(args)`; depois responde com o resultado da tool."""

    tool_name: str = ""
    tool_args: str = "{}"

    def _respond(self, messages: list[Any]) -> ModelResponse:
        tool_results = [m for m in messages if getattr(m, "role", None) == "tool"]
        if tool_results:
            return ModelResponse(role="assistant", content=f"resultado: {tool_results[-1].content}")
        return ModelResponse(
            role="assistant",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": self.tool_name, "arguments": self.tool_args},
                }
            ],
        )

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages") or (args[0] if args else []))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages") or (args[0] if args else []))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(kwargs.get("messages") or (args[0] if args else []))


def tool_args(**kwargs: Any) -> str:
    return json.dumps(kwargs)
