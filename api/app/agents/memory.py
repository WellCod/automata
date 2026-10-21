"""Memória do usuário entre sessões, por agente (ADR-0025).

O `MemoryManager` do Agno lê as memórias só por usuário: ligada em dois agentes,
a memória que um guardou iria para o contexto do outro. O manager daqui lê pelo
par usuário e agente. O banco que ele recebe mascara dados pessoais no texto da
memória e na mensagem de origem, que o Agno também grava, antes de qualquer
escrita: a máscara é a garantia, e a instrução de captura só reduz o que chega.
"""

from functools import lru_cache
from typing import Any

from agno.db.postgres import PostgresDb
from agno.db.schemas.memory import UserMemory
from agno.memory import MemoryManager

from app.guardrails.pii import find_pii, mask
from app.schemas.config import MemorySettings
from app.settings import get_settings

CAPTURE_RULES = (
    "Guarde só fatos estáveis e úteis para os próximos atendimentos deste usuário, como "
    "preferências e contexto que ele mesmo informou. Nunca guarde documento (CPF, RG, CNPJ), "
    "número de cartão, senha, dado bancário nem informação de saúde."
)


def _masked(text: str | None) -> str | None:
    if not text:
        return text
    return mask(text, find_pii(text))


class MaskingDb(PostgresDb):
    """PostgresDb que mascara PII de toda memória antes de gravar."""

    def upsert_user_memory(self, memory: UserMemory, *args: Any, **kwargs: Any) -> Any:
        memory.memory = _masked(memory.memory) or ""
        memory.input = _masked(memory.input)
        return super().upsert_user_memory(memory, *args, **kwargs)


@lru_cache(maxsize=1)
def _memory_db(db_url: str) -> MaskingDb:
    # um só: cada PostgresDb abre o próprio engine
    return MaskingDb(db_url=db_url)


def memory_db() -> MaskingDb:
    return _memory_db(get_settings().database_url)


class AgentMemoryManager(MemoryManager):
    """Lê só as memórias que este agente guardou para o usuário."""

    def __init__(self, agent_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.agent_id = agent_id

    def _read(self, user_id: str | None) -> dict[str, list[UserMemory]] | None:
        if self.db is None:
            return None
        rows = self.db.get_user_memories(user_id=user_id, agent_id=self.agent_id)
        memories: dict[str, list[UserMemory]] = {}
        # PostgresDb é síncrono e devolve UserMemory com deserialize padrão
        for memory in rows if isinstance(rows, list) else []:
            if not isinstance(memory, UserMemory):
                continue
            if memory.user_id is not None and memory.memory_id is not None:
                memories.setdefault(memory.user_id, []).append(memory)
        return memories

    def read_from_db(self, user_id: str | None = None) -> dict[str, list[UserMemory]] | None:
        return self._read(user_id)

    async def aread_from_db(self, user_id: str | None = None) -> dict[str, list[UserMemory]] | None:
        return self._read(user_id)


def memory_kwargs(agent_id: str, settings: MemorySettings, user_id: str | None) -> dict[str, Any]:
    """Argumentos do Agent para a memória; vazio quando ela não vale neste run.

    Sem usuário a memória fica desligada: o Agno usaria "default" e juntaria pessoas
    diferentes. Quem chama também não passa usuário nos runs da suíte de testes.
    """
    if not settings.enabled or not user_id:
        return {}
    instructions = CAPTURE_RULES
    if settings.instructions:
        instructions = f"{settings.instructions.strip()}\n\n{CAPTURE_RULES}"
    return {
        "memory_manager": AgentMemoryManager(
            agent_id=agent_id, db=memory_db(), memory_capture_instructions=instructions
        ),
        "update_memory_on_run": True,
        "add_memories_to_context": True,
    }
