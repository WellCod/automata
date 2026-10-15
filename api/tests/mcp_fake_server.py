"""Servidor MCP real (fastmcp, streamable-http) para testes de integração.

Exige `Authorization: Bearer <TOKEN>`, para os testes cobrirem o header
cifrado chegando ao servidor.
"""

import socket
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import uvicorn
from fastmcp import FastMCP

TOKEN = "token-de-teste"

mcp: FastMCP = FastMCP("crm-de-teste")
calls: list[tuple[str, dict[str, Any]]] = []


@mcp.tool
def buscar_cliente(cliente_id: str) -> str:
    """Busca o cadastro de um cliente pelo id."""
    calls.append(("buscar_cliente", {"cliente_id": cliente_id}))
    return f"cliente {cliente_id}: Maria, plano ouro"


@mcp.tool
def cancelar_assinatura(cliente_id: str) -> str:
    """Cancela a assinatura do cliente."""
    calls.append(("cancelar_assinatura", {"cliente_id": cliente_id}))
    return f"assinatura de {cliente_id} cancelada"


class _RequireToken:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            if headers.get(b"authorization") != f"Bearer {TOKEN}".encode():
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def running_server() -> Generator[str, None, None]:
    """Sobe o servidor numa thread e devolve a URL do endpoint MCP."""
    port = _free_port()
    app = _RequireToken(mcp.http_app(path="/mcp"))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("servidor MCP de teste não subiu")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
