"""Achados baixos de agentes da auditoria de 2026-11-16 (LLM-09, LLM-10, LLM-11)."""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.mcp.client import McpUnavailable, connect_strict


def test_erro_do_mcp_nao_volta_com_o_host_interno(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.mcp.client as mcp_client

    class Broken:
        initialized = False

        async def _connect(self) -> None:
            raise OSError("connect to 10.0.3.7:8080 refused")

        async def close(self) -> None:
            return None

    logged: list[dict[str, Any]] = []
    # o log do app pode não propagar para o caplog: captura direto no logger do módulo
    monkeypatch.setattr(
        mcp_client.logger, "warning", lambda msg, extra=None: logged.append(extra or {})
    )
    with pytest.raises(McpUnavailable) as exc:
        asyncio.run(connect_strict(Broken(), "crm"))  # type: ignore[arg-type]
    assert "10.0.3.7" not in str(exc.value)
    # o detalhe fica no log, como campo extra
    assert any("10.0.3.7" in str(e.get("error", "")) for e in logged)


def test_membro_do_time_grava_bloqueio_no_registro_do_lider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import uuid4

    import app.agents.factory as factory
    from app.schemas.config import ConfigPayload

    seen: list[Any] = []
    monkeypatch.setattr(
        factory, "pre_hooks_for", lambda cid, r, blocks, budget: seen.append(blocks)
    )
    payload = ConfigPayload(model_id="gpt-4o")
    member = factory.ResolvedVersion(name="m", description="m", payload=payload)
    leader_payload = ConfigPayload.model_validate(
        {"model_id": "gpt-4o", "team": {"members": [{"agent_id": str(uuid4())}]}}
    )
    leader = factory.ResolvedVersion(name="l", description="l", payload=leader_payload)
    resolved = factory.ResolvedTeam(leader=leader, members=[(uuid4(), member)])  # type: ignore[call-arg]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    team = factory.team_from(uuid4(), resolved)
    assert len(seen) == 2 and seen[0] is seen[1] is team.automata_blocks  # type: ignore[attr-defined]


def test_publicar_etapa_com_confirmacao_ve_o_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    from uuid import uuid4

    from app.schemas.config import ConfigKind
    from app.services.config import ConfigService

    agent_id = uuid4()

    def workflow_payload(version_id: object) -> dict[str, object]:
        step: dict[str, object] = {"type": "step", "name": "triagem", "agent_id": str(agent_id)}
        if version_id:
            step["version_id"] = str(version_id)
        return {"workflow": {"steps": [step]}}

    versions = {
        "v-livre": SimpleNamespace(payload=workflow_payload(None)),
        "v-fixa": SimpleNamespace(payload=workflow_payload(uuid4())),
    }
    workflows = [
        SimpleNamespace(name="Atendimento", current_version_id="v-livre"),
        SimpleNamespace(name="Cobrança", current_version_id="v-fixa"),
        SimpleNamespace(name="Rascunho", current_version_id=None),
    ]
    repo = SimpleNamespace(
        list_configs=lambda **kw: (workflows if kw.get("kind") == ConfigKind.workflow else [], 3),
        get_version=lambda vid: versions.get(vid),
    )
    service = ConfigService(repo)  # type: ignore[arg-type]
    # só o workflow que segue a vigente do agente passaria a rodar a tool com confirmação
    assert service._workflows_following(agent_id) == ["Atendimento"]
