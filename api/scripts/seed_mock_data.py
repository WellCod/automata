"""Insere dados mock de agent_run e usage_event para demonstrar o Analytics."""

import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://localhost/automata")
os.environ.setdefault("JWT_PRIVATE_KEY", "placeholder")
os.environ.setdefault("JWT_PUBLIC_KEY", "placeholder")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.models.run import AgentRun  # noqa: E402
from app.models.usage import UsageEvent  # noqa: E402

AGENT_IDS = [
    uuid.UUID("7603ddf0-2dd4-4831-b709-738ce934383f"),  # Analista Financeiro
    uuid.UUID("735cd1c5-0427-422e-9c20-04f90d2affd6"),  # Redator de Conteúdo
    uuid.UUID("ffe052ec-1856-4f58-875e-c47742302385"),  # Atendimento ao Cliente
    uuid.UUID("d5eae53b-6b7b-4b4e-8e36-1fbbfaf042ef"),  # Suporte ao Cliente
    uuid.UUID("b2c20158-cfcc-4fcb-89c6-7bf5647cc67f"),  # Assistente de Código
]

MODELS = {
    uuid.UUID("7603ddf0-2dd4-4831-b709-738ce934383f"): ("claude-opus-4-5", 0.015, 0.075),
    uuid.UUID("735cd1c5-0427-422e-9c20-04f90d2affd6"): ("claude-sonnet-4-5", 0.003, 0.015),
    uuid.UUID("ffe052ec-1856-4f58-875e-c47742302385"): ("claude-haiku-4-5", 0.00025, 0.00125),
    uuid.UUID("d5eae53b-6b7b-4b4e-8e36-1fbbfaf042ef"): ("claude-haiku-4-5", 0.00025, 0.00125),
    uuid.UUID("b2c20158-cfcc-4fcb-89c6-7bf5647cc67f"): ("claude-sonnet-4-5", 0.003, 0.015),
}

USERS = ["user_alice", "user_bob", "user_carol", "user_dave", "user_eve"]


def random_ts(days_back: int) -> datetime:
    offset = random.uniform(0, days_back * 24 * 3600)
    return datetime.now(UTC) - timedelta(seconds=offset)


def seed(session: Session, n_runs: int = 200) -> None:
    runs: list[AgentRun] = []
    events: list[UsageEvent] = []

    for _ in range(n_runs):
        agent_id = random.choice(AGENT_IDS)
        model_id, price_in, price_out = MODELS[agent_id]
        ts = random_ts(days_back=60)
        period = ts.strftime("%Y%m")

        # 8% taxa de erro, tempo de resposta variado por agente
        status = "error" if random.random() < 0.08 else "success"
        duration_ms = int(random.gauss(
            mu={"Analista": 3200, "Redator": 2800, "Atendimento": 1200,
                "Suporte": 1100, "Assistente": 2400}.get(
                    next((k for k in ["Analista", "Redator", "Atendimento", "Suporte", "Assistente"]
                          if k in str(agent_id)), "Suporte"), 1500),
            sigma=600,
        ))
        duration_ms = max(300, duration_ms)

        run = AgentRun(
            id=uuid.uuid4(),
            agent_config_id=agent_id,
            user_id=random.choice(USERS),
            run_id=str(uuid.uuid4()),
            status=status,
            duration_ms=duration_ms if status == "success" else None,
            error="LLM timeout" if status == "error" else None,
            created_at=ts,
        )
        runs.append(run)

        if status == "success":
            in_tok = random.randint(200, 1500)
            out_tok = random.randint(100, 800)
            cost = round((in_tok / 1000) * price_in + (out_tok / 1000) * price_out, 8)
            events.append(UsageEvent(
                id=uuid.uuid4(),
                agent_config_id=agent_id,
                user_id=run.user_id,
                run_id=run.run_id,
                model_id=model_id,
                period=period,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=in_tok + out_tok,
                cost=cost,
                created_at=ts,
            ))

    session.add_all(runs)
    session.add_all(events)
    session.commit()
    print(f"Inseridos {len(runs)} runs e {len(events)} usage events.")


if __name__ == "__main__":
    with Session(get_engine()) as session:
        seed(session)
