"""Worker de ingestão separado (ADR-0039): `python -m app.knowledge.worker`.

Reivindica com `FOR UPDATE SKIP LOCKED`, então várias réplicas dividem a fila. O job
travado há mais de 30 minutos (worker caiu no meio) volta para a fila uma vez e, na
segunda, falha junto com o conteúdo ou o conector.
"""

import logging
import signal
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import FrameType
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.jobs import CONTENT_KINDS, execute, fail_content
from app.logging_config import configure_logging
from app.models.ingest_job import IngestJob
from app.models.knowledge_connector import KnowledgeConnector

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=30)
# a primeira queda devolve o job à fila; a segunda falha de vez
MAX_ATTEMPTS = 2
# jobs concluídos ou falhos ficam na tabela por este tempo, para consulta
KEEP_FINISHED = timedelta(days=7)
POLL_SECONDS = 2.0
# bem abaixo do STALE_AFTER: um batimento perdido não devolve o job à fila
HEARTBEAT_SECONDS = 300.0


@dataclass(frozen=True)
class Claimed:
    id: UUID
    kind: str
    target_id: UUID
    payload: dict[str, Any] | None


def _fail_target(kind: str, target_id: UUID, message: str) -> None:
    """Leva a falha do job ao alvo (conteúdo ou conector), onde o painel mostra."""
    if kind in CONTENT_KINDS:
        fail_content(target_id, message)
    elif kind == "sync":
        with Session(get_engine()) as session:
            session.execute(
                update(KnowledgeConnector)
                .where(KnowledgeConnector.id == target_id)
                .values(last_status="failed", last_message=message[:500])
            )
            session.commit()


def recover_stale(now: datetime | None = None) -> tuple[int, int]:
    """Devolve à fila o job travado; o que já tinha voltado uma vez falha."""
    limit = (now or datetime.now(UTC)) - STALE_AFTER
    requeued = failed = 0
    with Session(get_engine()) as session:
        stale = list(
            session.scalars(
                select(IngestJob)
                .where(IngestJob.status == "running", IngestJob.started_at < limit)
                .with_for_update(skip_locked=True)
            )
        )
        to_fail: list[tuple[str, UUID]] = []
        for job in stale:
            if job.attempts < MAX_ATTEMPTS:
                job.status = "queued"
                job.started_at = None
                requeued += 1
            else:
                job.status = "failed"
                job.error = "interrompido duas vezes no worker"
                job.finished_at = datetime.now(UTC)
                to_fail.append((job.kind, job.target_id))
                failed += 1
        session.commit()
    for kind, target_id in to_fail:
        _fail_target(kind, target_id, "interrompido duas vezes no worker de ingestão; reenvie")
    return requeued, failed


def claim(now: datetime | None = None) -> Claimed | None:
    """Reivindica o job mais antigo da fila; None quando a fila está vazia."""
    with Session(get_engine()) as session:
        job = session.scalars(
            select(IngestJob)
            .where(IngestJob.status == "queued")
            .order_by(IngestJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        job.started_at = now or datetime.now(UTC)
        session.commit()
        return Claimed(job.id, job.kind, job.target_id, job.payload)


def _finish(job_id: UUID, status: str, error: str | None = None) -> None:
    """Grava o fim do job."""
    with Session(get_engine()) as session:
        session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(status=status, error=error, finished_at=datetime.now(UTC))
        )
        session.commit()


def _heartbeat(job_id: UUID, stop: threading.Event) -> None:
    """Renova o `started_at` enquanto o job roda: job longo não volta à fila no meio (Fase 43)."""
    while not stop.wait(HEARTBEAT_SECONDS):
        try:
            with Session(get_engine()) as session:
                session.execute(
                    update(IngestJob)
                    .where(IngestJob.id == job_id, IngestJob.status == "running")
                    .values(started_at=datetime.now(UTC))
                )
                session.commit()
        except Exception as exc:
            logger.warning("batimento do job falhou", extra={"error": str(exc)})


def run_once() -> bool:
    """Executa um job; devolve se havia algum."""
    job = claim()
    if job is None:
        return False
    log_extra = {"job_id": str(job.id), "kind": job.kind, "target_id": str(job.target_id)}
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat, args=(job.id, stop_heartbeat), daemon=True
    )
    heartbeat_thread.start()
    try:
        execute(job.kind, job.target_id, job.payload)
    except Exception as exc:
        # os caminhos gravam a própria falha; aqui fica o que escapou deles
        logger.exception("job de ingestão falhou", extra=log_extra)
        _finish(job.id, "failed", str(exc)[:500])
        _fail_target(job.kind, job.target_id, f"falha na ingestão: {exc}")
        return True
    finally:
        stop_heartbeat.set()
    _finish(job.id, "done")
    logger.info("job de ingestão concluído", extra=log_extra)
    return True


def purge_finished(now: datetime | None = None) -> int:
    """Apaga os jobs terminados há mais de `KEEP_FINISHED`; devolve quantos saíram."""
    limit = (now or datetime.now(UTC)) - KEEP_FINISHED
    with Session(get_engine()) as session:
        result = session.execute(
            delete(IngestJob).where(
                IngestJob.status.in_(["done", "failed"]), IngestJob.finished_at < limit
            )
        )
        session.commit()
        return int(getattr(result, "rowcount", 0) or 0)


class _Stop:
    """Tratador de SIGTERM e SIGINT que só pede a parada ao laço principal."""

    requested = False

    def __call__(self, signum: int, frame: FrameType | None) -> None:
        # termina o job em andamento antes de sair
        self.requested = True


def main() -> None:
    """Laço do worker: manutenção da fila a cada minuto e um job por volta."""
    configure_logging()
    stop = _Stop()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("worker de ingestão no ar")
    last_maintenance = 0.0
    while not stop.requested:
        if time.monotonic() - last_maintenance > 60:
            try:
                requeued, failed = recover_stale()
                if requeued or failed:
                    logger.warning(
                        "jobs travados revistos", extra={"requeued": requeued, "failed": failed}
                    )
                purge_finished()
            except Exception as exc:
                logger.warning("manutenção da fila falhou", extra={"error": str(exc)})
            last_maintenance = time.monotonic()
        try:
            worked = run_once()
        except Exception as exc:
            # banco fora do ar: espera e tenta de novo
            logger.warning("fila de ingestão indisponível", extra={"error": str(exc)})
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)
    logger.info("worker de ingestão parado")


if __name__ == "__main__":
    main()
