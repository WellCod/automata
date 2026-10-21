"""Evals da memória do usuário (ADR-0025).

Sem banco e sem rede: rodam em todo PR. Errar aqui é guardar documento de cliente,
mostrar a um agente o que outro guardou ou manter memória além do prazo.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from agno.db.schemas.memory import UserMemory

from app.agents.memory import CAPTURE_RULES, AgentMemoryManager, _masked, memory_kwargs
from app.agents.memory_admin import expired
from app.schemas.config import MemorySettings


@pytest.mark.parametrize(
    ("text", "leaked"),
    [
        ("CPF 529.982.247-25", "529.982.247-25"),
        ("cpf 52998224725", "52998224725"),
        ("CNPJ 11.222.333/0001-81", "11.222.333/0001-81"),
        ("cartão 4111 1111 1111 1111", "4111 1111 1111 1111"),
        ("e-mail ana@exemplo.com", "ana@exemplo.com"),
        ("telefone (11) 98765-4321", "98765-4321"),
    ],
)
def test_dado_pessoal_nunca_chega_inteiro_na_memoria(text: str, leaked: str) -> None:
    masked = _masked(text)
    assert masked is not None and leaked not in masked


def test_texto_sem_dado_pessoal_fica_igual() -> None:
    assert _masked("Prefere entrega à tarde e veste M") == "Prefere entrega à tarde e veste M"
    assert _masked(None) is None


@pytest.mark.parametrize(
    ("enabled", "user", "on"),
    [(True, "cliente", True), (True, None, False), (True, "", False), (False, "cliente", False)],
)
def test_memoria_so_com_usuario_identificado(enabled: bool, user: str | None, on: bool) -> None:
    kwargs = memory_kwargs("agente", MemorySettings(enabled=enabled), user)
    assert bool(kwargs) is on


def test_instrucoes_de_captura_sempre_levam_as_regras() -> None:
    plain = memory_kwargs("a", MemorySettings(enabled=True), "u")["memory_manager"]
    assert plain.memory_capture_instructions == CAPTURE_RULES
    custom = memory_kwargs("a", MemorySettings(enabled=True, instructions="  tamanho "), "u")
    text = custom["memory_manager"].memory_capture_instructions
    assert text.startswith("tamanho") and text.endswith(CAPTURE_RULES)


class FakeDb:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_user_memories(self, **kwargs: Any) -> list[UserMemory]:
        self.calls.append(kwargs)
        return [
            UserMemory(memory="veste M", memory_id="1", user_id="ana", agent_id="loja"),
            # linha sem id: o Agno também ignora
            UserMemory(memory="sem id", user_id="ana", agent_id="loja"),
        ]


def test_leitura_sempre_pelo_par_usuario_e_agente() -> None:
    db = FakeDb()
    manager = AgentMemoryManager(agent_id="loja", db=db)  # type: ignore[arg-type]
    found = manager.read_from_db(user_id="ana")
    assert db.calls == [{"user_id": "ana", "agent_id": "loja"}]
    assert found is not None and [m.memory for m in found["ana"]] == ["veste M"]
    # sem usuário também filtra pelo agente: nunca devolve memória de outro
    manager.get_user_memories(user_id=None)
    assert db.calls[-1]["agent_id"] == "loja"


def test_vencimento_conta_da_ultima_atualizacao() -> None:
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)

    def at(days: float) -> int:
        return int((now - timedelta(days=days)).timestamp())

    rows = [
        UserMemory(memory="velha", memory_id="v", created_at=at(100), updated_at=at(100)),
        # criada há muito, atualizada ontem: fica
        UserMemory(memory="renovada", memory_id="r", created_at=at(100), updated_at=at(1)),
        UserMemory(memory="sem data de atualização", memory_id="c", created_at=at(100)),
        UserMemory(memory="no limite", memory_id="l", updated_at=at(89.9)),
    ]
    assert expired(rows, 90, now) == ["v", "c"]
