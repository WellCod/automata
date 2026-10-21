"""Fila durável dos runs em background (ADR-0020), fora de app.main para não montar o app."""

from agno.job_queue.config import QueueConfig

from app.settings import Settings

# fixos no código, não por variável: o Agno exige o mesmo valor em todas as réplicas
QUEUE_TIMEOUT_S = 900
QUEUE_MAX_ATTEMPTS = 1


def background_queue(settings: Settings) -> QueueConfig | None:
    """Fila durável dos runs em background (ADR-0020); None deixa as tasks em memória.

    Uma tentativa: o agente pode ter chamado tool com efeito antes de cair, e rodar de
    novo sozinho repetiria o efeito. Com Redis, cancelar e acompanhar valem entre réplicas.
    """
    if not settings.background_queue_durable:
        return None
    return QueueConfig(
        durable=True,
        max_attempts=QUEUE_MAX_ATTEMPTS,
        timeout_seconds=QUEUE_TIMEOUT_S,
        redis=settings.redis_url or None,
    )
