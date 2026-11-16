"""Fecha toda conexão WebSocket.

O AgentOS monta `/workflows/ws`, e middleware HTTP do Starlette não roda em scope
WebSocket: a revogação de token e a trilha não alcançariam o canal. O painel não usa.
"""

from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send


class NoWebSocketMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            # fechar antes do accept vira 403 no handshake; 1008 = violação de política
            message: dict[str, Any] = {"type": "websocket.close", "code": 1008}
            await send(message)
            return
        await self.app(scope, receive, send)
