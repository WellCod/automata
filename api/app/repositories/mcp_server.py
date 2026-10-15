from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mcp_server import McpServer


class McpServerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[McpServer]:
        return list(self._session.scalars(select(McpServer).order_by(McpServer.name)))

    def get(self, server_id: UUID) -> McpServer | None:
        return self._session.get(McpServer, server_id)

    def get_many(self, server_ids: list[UUID]) -> list[McpServer]:
        if not server_ids:
            return []
        return list(self._session.scalars(select(McpServer).where(McpServer.id.in_(server_ids))))

    def find_conflict(self, name: str, slug: str, exclude: UUID | None = None) -> McpServer | None:
        stmt = select(McpServer).where((McpServer.name == name) | (McpServer.slug == slug))
        if exclude is not None:
            stmt = stmt.where(McpServer.id != exclude)
        return self._session.scalars(stmt).first()

    def add(self, server: McpServer) -> McpServer:
        self._session.add(server)
        self._session.flush()
        return server

    def delete(self, server: McpServer) -> None:
        self._session.delete(server)
        self._session.flush()
