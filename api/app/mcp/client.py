"""Conexão com servidores MCP externos (ADR-0010)."""

import asyncio
import contextlib
from datetime import timedelta

from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import StreamableHTTPClientParams

from app.mcp.egress import check_url
from app.models.mcp_server import McpServer
from app.schemas.mcp_server import McpToolInfo
from app.secrets import decrypt_json


class McpUnavailable(RuntimeError):
    """Servidor MCP que não conectou: o run deve falhar em vez de seguir sem as tools."""


def build_mcp_tools(
    server: McpServer,
    *,
    include_tools: list[str] | None = None,
    requires_confirmation: list[str] | None = None,
) -> MCPTools:
    """MCPTools de um servidor cadastrado: só streamable-http, prefixo pelo slug."""
    check_url(server.url)
    headers = decrypt_json(server.headers_encrypted) if server.headers_encrypted else None
    params = StreamableHTTPClientParams(
        url=server.url,
        headers=headers,
        timeout=timedelta(seconds=server.timeout_seconds),
    )
    return MCPTools(
        name=f"mcp_{server.slug}",
        transport="streamable-http",
        server_params=params,
        timeout_seconds=server.timeout_seconds,
        tool_name_prefix=server.slug,
        include_tools=include_tools,
        requires_confirmation_tools=requires_confirmation or [],
    )


async def connect_strict(tools: MCPTools, label: str) -> None:
    """Conecta e falha alto.

    `MCPTools.connect()` engole a exceção e só loga, e o Agent roda sem as
    tools. Aqui chamamos o `_connect` interno (agno==2.8.7, fixado) para
    propagar o motivo — 401, timeout, tool inexistente no include.
    """
    if tools.initialized:
        return
    task = asyncio.current_task()
    baseline = task.cancelling() if task is not None else 0
    try:
        await tools._connect()
    except asyncio.CancelledError as exc:
        # 401 ou conexão recusada: o task group do cliente streamable-http cancela
        # a task que conectou, porque o Agno mantém o contexto aberto fora do
        # `async with`. Cancelamento externo (cliente desconectou) é repassado.
        if task is None or task.cancelling() <= baseline:
            raise
        while task.cancelling() > baseline:
            task.uncancel()
        await _cleanup(tools)
        raise McpUnavailable(f"servidor MCP '{label}' indisponível") from exc
    except Exception as exc:
        await _cleanup(tools)
        raise McpUnavailable(f"servidor MCP '{label}' indisponível: {exc}") from exc
    if not tools.initialized:
        raise McpUnavailable(f"servidor MCP '{label}' indisponível")


async def _cleanup(tools: MCPTools) -> None:
    # best-effort: a conexão já falhou
    with contextlib.suppress(Exception):
        await tools._safe_cleanup()


async def discover_tools(server: McpServer) -> list[McpToolInfo]:
    """Conecta, lista as tools (nomes sem prefixo) e fecha."""
    # check_url resolve DNS: fora do event loop
    tools = await asyncio.to_thread(build_mcp_tools, server)
    await connect_strict(tools, server.slug)
    try:
        prefix = f"{server.slug}_"
        return [
            McpToolInfo(
                name=name.removeprefix(prefix),
                description=fn.description,
                input_schema=fn.parameters or {},
            )
            for name, fn in tools.functions.items()
        ]
    finally:
        await tools.close()
