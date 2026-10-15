"""Cenário de tracing executado em processo próprio por tests/test_traces.py.

Liga o tracing (provider global do OpenTelemetry), publica um agente com tool
MCP e um time, roda o time e imprime a árvore de `/api/v1/runs/{id}/trace` em
JSON. Uso: python -m tests.trace_scenario <database_url>
"""

import json
import os
import sys


def main(database_url: str) -> None:
    from cryptography.fernet import Fernet

    os.environ.update(
        {
            "DATABASE_URL": database_url,
            "JWT_PRIVATE_KEY": "x",
            "JWT_PUBLIC_KEY": "x",
            "TRACING_ENABLED": "true",
            "MCP_SECRETS_KEY": Fernet.generate_key().decode(),
            "MCP_ALLOWED_HOSTS": "127.0.0.1",
        }
    )
    from fastapi.testclient import TestClient

    import app.agents.factory as factory
    from app.main import create_app
    from tests.fake_models import DelegatingModel, tool_args
    from tests.mcp_fake_server import TOKEN, running_server

    model = DelegatingModel(id="claude-haiku-4-5")
    factory.resolve_model = lambda *a, **k: model  # type: ignore[assignment]

    with running_server() as mcp_url:
        app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        with TestClient(app) as client:
            server = client.post(
                "/api/v1/mcp-servers",
                json={
                    "name": "crm",
                    "slug": "crm",
                    "url": mcp_url,
                    "headers": {"Authorization": f"Bearer {TOKEN}"},
                },
            ).json()
            client.post(f"/api/v1/mcp-servers/{server['id']}/discover").raise_for_status()

            def publish(kind: str, name: str, payload: dict[str, object]) -> str:
                body = {"name": name, "description": f"Use para {name}"}
                config_id = client.post("/api/v1/configs", json={**body, "kind": kind}).json()["id"]
                client.put(
                    f"/api/v1/configs/{config_id}/draft", json={**body, "payload": payload}
                ).raise_for_status()
                client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
                return str(config_id)

            membro = publish(
                "agent",
                "consulta",
                {
                    "model_id": "claude-haiku-4-5",
                    "mcp_servers": [{"server_id": server["id"], "tools": ["buscar_cliente"]}],
                },
            )
            model.member_id = membro
            model.member_tool = "crm_buscar_cliente"
            model.member_tool_args = tool_args(cliente_id="42")
            time = publish(
                "team",
                "atendimento",
                {"model_id": "claude-haiku-4-5", "team": {"members": [{"agent_id": membro}]}},
            )
            run = client.post(f"/teams/{time}/runs", data={"message": "oi", "stream": "false"})
            run.raise_for_status()
            trace = client.get(f"/api/v1/runs/{run.json()['run_id']}/trace")
            print("TRACE_JSON=" + json.dumps({"status": trace.status_code, "body": trace.json()}))


if __name__ == "__main__":
    main(sys.argv[1])
