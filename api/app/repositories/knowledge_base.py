from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models.config import AgentConfig, AgentConfigVersion
from app.models.knowledge_base import KnowledgeBase

VECTOR_SCHEMA = "ai"


class KnowledgeBaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[KnowledgeBase]:
        return list(self._session.scalars(select(KnowledgeBase).order_by(KnowledgeBase.name)))

    def get(self, base_id: UUID) -> KnowledgeBase | None:
        return self._session.get(KnowledgeBase, base_id)

    def get_many(self, base_ids: list[UUID]) -> list[KnowledgeBase]:
        if not base_ids:
            return []
        return list(
            self._session.scalars(select(KnowledgeBase).where(KnowledgeBase.id.in_(base_ids)))
        )

    def find_conflict(
        self, name: str, slug: str | None = None, exclude: UUID | None = None
    ) -> KnowledgeBase | None:
        cond = KnowledgeBase.name == name
        if slug is not None:
            cond = cond | (KnowledgeBase.slug == slug)
        stmt = select(KnowledgeBase).where(cond)
        if exclude is not None:
            stmt = stmt.where(KnowledgeBase.id != exclude)
        return self._session.scalars(stmt).first()

    def used_by(self, base_id: UUID) -> list[str]:
        """Agentes e times cuja versão vigente ou rascunho consulta a base."""
        stmt = (
            select(AgentConfig.name)
            .join(
                AgentConfigVersion,
                or_(
                    AgentConfigVersion.id == AgentConfig.current_version_id,
                    AgentConfigVersion.id == AgentConfig.draft_version_id,
                ),
            )
            .where(AgentConfigVersion.payload["knowledge"].contains([{"base_id": str(base_id)}]))
            .distinct()
            .order_by(AgentConfig.name)
        )
        return list(self._session.scalars(stmt))

    def add(self, base: KnowledgeBase) -> KnowledgeBase:
        self._session.add(base)
        self._session.flush()
        return base

    def delete(self, base: KnowledgeBase) -> None:
        # vector_table é gerado pela API (kb_<hex do id>), nunca vem do usuário
        self._session.execute(text(f'DROP TABLE IF EXISTS "{VECTOR_SCHEMA}"."{base.vector_table}"'))
        self._session.delete(base)
        self._session.flush()
