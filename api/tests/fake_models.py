"""Modelos falsos para testes de runtime: chamam uma tool e depois respondem."""

import json
from dataclasses import dataclass
from typing import Any

from agno.metrics import MessageMetrics
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


@dataclass
class CountingModel(ReplayModel):
    """Responde quantas mensagens do usuário chegaram: mostra se o histórico foi junto."""

    def _respond(self, messages: Any) -> ModelResponse:
        users = [m for m in messages or [] if getattr(m, "role", None) == "user"]
        return ModelResponse(role="assistant", content=f"mensagens: {len(users)}")

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(kwargs.get("messages"))


@dataclass
class SummarizingModel(ReplayModel):
    """Conversa longa de mentira: respostas grandes, um resumo no pedido de compactação.

    A resposta normal diz se o resumo chegou nas mensagens, para o teste ver que o
    começo da conversa continua chegando ao modelo depois de sair da janela.
    """

    filler: str = "lorem ipsum " * 600
    summary: str = "RESUMO: o cliente informou o pedido 123."

    def _respond(self, messages: Any) -> ModelResponse:
        texts = [str(getattr(m, "content", "") or "") for m in messages or []]
        usage = MessageMetrics(input_tokens=50, output_tokens=20, total_tokens=70)
        if any("running summary of a long conversation" in t for t in texts):
            return ModelResponse(role="assistant", content=self.summary, response_usage=usage)
        seen = "viu-resumo" if any(self.summary in t for t in texts) else "sem-resumo"
        return ModelResponse(
            role="assistant", content=f"{seen} {self.filler}", response_usage=usage
        )

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(kwargs.get("messages"))


@dataclass
class FixedReplyModel(ReplayModel):
    """Responde sempre o mesmo texto."""

    reply: str = ""
    # tokens de saída por resposta; 0 não grava usage_event
    tokens: int = 0

    def _respond(self) -> ModelResponse:
        usage = MessageMetrics(output_tokens=self.tokens, total_tokens=self.tokens)
        return ModelResponse(
            role="assistant", content=self.reply, response_usage=usage if self.tokens else None
        )

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond()

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond()

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond()
