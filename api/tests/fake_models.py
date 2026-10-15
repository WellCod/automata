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


@dataclass
class DelegatingModel(ReplayModel):
    """Serve de líder e de membro: decide pelas tools que recebeu nesta chamada.

    Com `delegate_task_to_member` disponível, delega ao `member_id`; com a tool
    `member_tool`, chama ela; depois de qualquer resultado de tool, responde.
    """

    member_id: str = ""
    member_tool: str = ""
    member_tool_args: str = "{}"

    def _respond(self, messages: list[Any], tools: list[Any]) -> ModelResponse:
        tool_results = [m for m in messages if getattr(m, "role", None) == "tool"]
        if tool_results:
            return ModelResponse(role="assistant", content=f"resultado: {tool_results[-1].content}")
        names = {
            (t.get("function") or {}).get("name") if isinstance(t, dict) else None for t in tools
        }
        if "delegate_task_to_member" in names:
            call = (
                "delegate_task_to_member",
                json.dumps({"member_id": self.member_id, "task": "busque o cliente 42"}),
            )
        elif self.member_tool in names:
            call = (self.member_tool, self.member_tool_args)
        else:
            return ModelResponse(role="assistant", content="sem ferramenta para isso")
        return ModelResponse(
            role="assistant",
            tool_calls=[
                {
                    "id": "call_x",
                    "type": "function",
                    "function": {"name": call[0], "arguments": call[1]},
                }
            ],
        )

    def _args(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[list[Any], list[Any]]:
        messages = kwargs.get("messages") or (args[0] if args else [])
        return messages, kwargs.get("tools") or []

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(*self._args(args, kwargs))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(*self._args(args, kwargs))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(*self._args(args, kwargs))
