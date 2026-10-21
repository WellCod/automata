"""Evals da compactação de conversa (ADR-0019): o que liga, com que limite e o que fica igual.

Sem banco e sem LLM. O teste de ponta a ponta, com resumo chegando ao modelo, está em
test_factory_runtime.py; aqui ficam as regras que, mudando em silêncio, encarecem
toda conversa ou mudam agente publicado sem nova versão.
"""

import pytest
from pydantic import ValidationError

from app.agents.factory import compaction_for
from app.schemas.config import ConfigPayload, ConversationSettings


def test_versao_sem_a_secao_fica_sem_compactacao() -> None:
    payload = ConfigPayload.model_validate({"schema_version": 2, "model_id": "claude-haiku-4-5"})
    assert payload.conversation.compaction is False
    assert compaction_for(payload.conversation) is None


def test_ligada_passa_limite_turnos_e_instrucoes_ao_agno() -> None:
    settings = ConversationSettings(
        compaction=True,
        compact_at_tokens=8_000,
        keep_recent_runs=2,
        summary_instructions="mantenha números de pedido",
        search_history=False,
    )
    compaction = compaction_for(settings)
    assert compaction is not None
    assert compaction.compact_at_tokens == 8_000
    assert compaction.uncompacted_runs == 2
    assert compaction.instructions == "mantenha números de pedido"
    assert compaction.search_compacted_messages is False
    # o resumo é do modelo do próprio agente: nada de modelo padrão do Agno
    assert compaction.model is None


def test_padrao_bem_abaixo_do_agno() -> None:
    # 150 mil do Agno quase nunca resumiria e mandaria o histórico inteiro até lá
    assert ConversationSettings(compaction=True).compact_at_tokens == 16_000


@pytest.mark.parametrize(
    "fields",
    [
        {"compact_at_tokens": 3_999},
        {"compact_at_tokens": 128_001},
        {"keep_recent_runs": 0},
        {"keep_recent_runs": 21},
        {"summary_instructions": "x" * 501},
    ],
)
def test_limites_recusados_na_escrita(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ConversationSettings(compaction=True, **fields)  # type: ignore[arg-type]
