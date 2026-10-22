"""Sincronização de um conector com a base (ADR-0024).

Compara pela versão remota: arquivo novo é ingerido, versão mudada é reindexada
(os trechos antigos saem antes), arquivo que sumiu da origem sai da base e
versão igual não baixa de novo. Roda em background e nunca levanta: o resultado
fica no próprio conector.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.ingest import ingest, remove_chunks
from app.knowledge.sources import SUPPORTED, RemoteFile, Source, SourceError, source_for
from app.mcp.egress import EgressDenied
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_connector import KnowledgeConnector
from app.models.knowledge_content import KnowledgeContent
from app.secrets import SecretsKeyMissing, decrypt_json
from app.settings import get_settings

logger = logging.getLogger(__name__)

MAX_FILES = 500
_MAX_MESSAGE = 500


@dataclass
class SyncSummary:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    failed: int = 0
    # fora da sincronização: extensão que a ingestão não lê, arquivo grande, acima do limite
    skipped: int = 0
    truncated: bool = False
    errors: list[str] = field(default_factory=list)


def secret_of(connector: KnowledgeConnector) -> dict[str, str]:
    return decrypt_json(connector.secret_encrypted) if connector.secret_encrypted else {}


def source_of(connector: KnowledgeConnector) -> Source:
    return source_for(connector.kind, connector.settings, secret_of(connector))


def selectable(files: list[RemoteFile], max_bytes: int) -> tuple[list[RemoteFile], int]:
    """Arquivos que entram e quantos ficaram de fora."""
    chosen = [f for f in files if f.extension in SUPPORTED and 0 < f.size <= max_bytes]
    skipped = len(files) - len(chosen)
    if len(chosen) > MAX_FILES:
        skipped += len(chosen) - MAX_FILES
        chosen = sorted(chosen, key=lambda f: f.path)[:MAX_FILES]
    return chosen, skipped


def _finish(connector_id: UUID, status: str, message: str | None, summary: SyncSummary) -> None:
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeConnector)
            .where(KnowledgeConnector.id == connector_id)
            .values(
                last_status=status,
                last_message=message[:_MAX_MESSAGE] if message else None,
                last_summary=asdict(summary),
                last_sync_at=datetime.now(UTC),
            )
        )
        session.commit()


def _status_of(content_id: UUID) -> str:
    with Session(get_engine()) as session:
        content = session.get(KnowledgeContent, content_id)
        return content.status if content is not None else "failed"


def _upsert(
    connector: KnowledgeConnector, base: KnowledgeBase, file: RemoteFile, existing: UUID | None
) -> UUID:
    """Registra o arquivo como processing; o existente perde os trechos antigos antes."""
    with Session(get_engine()) as session:
        if existing is not None:
            remove_chunks(base, existing)
            session.execute(
                update(KnowledgeContent)
                .where(KnowledgeContent.id == existing)
                .values(
                    status="processing",
                    status_message=None,
                    chunk_count=0,
                    external_version=file.version,
                    size_bytes=file.size,
                )
            )
            session.commit()
            return existing
        content = KnowledgeContent(
            base_id=base.id,
            name=file.name[:255],
            source_type="connector",
            source=f"{source_of(connector).label}/{file.path}"[:2048],
            extension=file.extension,
            size_bytes=file.size,
            status="processing",
            created_by=connector.created_by,
            connector_id=connector.id,
            external_path=file.path,
            external_version=file.version,
        )
        session.add(content)
        session.commit()
        return content.id


def sync(connector_id: UUID) -> SyncSummary:
    summary = SyncSummary()
    try:
        with Session(get_engine()) as session:
            connector = session.get(KnowledgeConnector, connector_id)
            base = session.get(KnowledgeBase, connector.base_id) if connector else None
            if connector is None or base is None:
                return summary
            known = {
                c.external_path: (c.id, c.external_version, c.status)
                for c in session.scalars(
                    select(KnowledgeContent).where(KnowledgeContent.connector_id == connector_id)
                )
                if c.external_path is not None
            }
            session.expunge_all()
        source = source_of(connector)
        listed = source.list_files()
        summary.truncated = source.truncated
        max_bytes = get_settings().knowledge_max_upload_mb * 1024 * 1024
        files, summary.skipped = selectable(listed, max_bytes)
        seen: set[str] = set()
        for file in files:
            seen.add(file.path)
            current = known.get(file.path)
            if current is not None and current[1] == file.version and current[2] == "completed":
                summary.unchanged += 1
                continue
            try:
                data = source.download(file)
            except (SourceError, EgressDenied) as exc:
                summary.failed += 1
                summary.errors.append(f"{file.path}: {exc}"[:200])
                continue
            content_id = _upsert(connector, base, file, current[0] if current else None)
            ingest(content_id, data)
            if _status_of(content_id) != "completed":
                summary.failed += 1
            elif current is None:
                summary.added += 1
            else:
                summary.updated += 1
        # sumiu da origem: sai da base, com os trechos
        gone = [cid for path, (cid, _, _) in known.items() if path not in seen]
        if gone:
            for cid in gone:
                remove_chunks(base, cid)
            with Session(get_engine()) as session:
                for cid in gone:
                    row = session.get(KnowledgeContent, cid)
                    if row is not None:
                        session.delete(row)
                session.commit()
            summary.removed = len(gone)
    except (SourceError, EgressDenied, SecretsKeyMissing) as exc:
        logger.warning(
            "conector falhou", extra={"connector_id": str(connector_id), "error": str(exc)}
        )
        _finish(connector_id, "failed", str(exc), summary)
        return summary
    except Exception as exc:
        logger.exception("sincronização falhou", extra={"connector_id": str(connector_id)})
        _finish(connector_id, "failed", f"{type(exc).__name__}: {exc}", summary)
        return summary
    status = "failed" if summary.failed and not (summary.added or summary.updated) else "ok"
    _finish(connector_id, status, None, summary)
    logger.info(
        "conector sincronizado", extra={"connector_id": str(connector_id), **asdict(summary)}
    )
    return summary
