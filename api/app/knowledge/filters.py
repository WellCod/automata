"""Campos dos documentos e filtros escolhidos pelo modelo na busca (ADR-0033).

Os campos ficam no `knowledge_content.fields` e em `meta_data.fields` de cada trecho.
O `PgVector.search` aplica filtro em dict como `meta_data @> filtro`.
"""

import json
import time
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.runtime import vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent

# valores listados por campo na descrição da tool
MAX_VALUES = 20
_TTL = 60.0
_cache: dict[UUID, tuple[float, dict[str, list[str]]]] = {}


def field_values(base_id: UUID) -> dict[str, list[str]]:
    """Campos e até 20 valores de cada um, dos documentos prontos da base, com cache curto."""
    cached = _cache.get(base_id)
    if cached and time.monotonic() - cached[0] < _TTL:
        return cached[1]
    pairs = func.jsonb_each_text(KnowledgeContent.fields).table_valued("key", "value")
    with Session(get_engine()) as session:
        rows = session.execute(
            select(pairs.c.key, pairs.c.value)
            .select_from(KnowledgeContent)
            .join(pairs, text("true"))
            .where(
                KnowledgeContent.base_id == base_id,
                KnowledgeContent.status == "completed",
                KnowledgeContent.fields.is_not(None),
            )
            .distinct()
            .order_by(pairs.c.key, pairs.c.value)
        ).all()
    values: dict[str, list[str]] = {}
    for key, value in rows:
        bucket = values.setdefault(str(key), [])
        if len(bucket) < MAX_VALUES:
            bucket.append(str(value))
    _cache[base_id] = (time.monotonic(), values)
    return values


def forget_field_values(base_id: UUID) -> None:
    _cache.pop(base_id, None)


def set_chunk_fields(base: KnowledgeBase, content_id: UUID, fields: dict[str, str]) -> None:
    """Troca os campos nos trechos já indexados, sem embedar de novo."""
    vector_db = vector_db_for(base)
    if not vector_db.table_exists():
        return
    table = vector_db.table
    with Session(get_engine()) as session:
        session.execute(
            table.update()
            .where(table.c.content_id == str(content_id))
            .values(
                meta_data=func.jsonb_set(
                    func.coalesce(table.c.meta_data, text("'{}'::jsonb")),
                    text("'{fields}'"),
                    bindparam("fields", fields, type_=JSONB),
                )
            )
        )
        session.commit()


def clean_filters(
    requested: dict[str, Any] | None, known: dict[str, list[str]]
) -> tuple[dict[str, str], list[str]]:
    """Fica o que existe na base; o resto vira aviso para o modelo."""
    kept: dict[str, str] = {}
    ignored: list[str] = []
    for key, raw in (requested or {}).items():
        value = str(raw).strip()
        if key in known and value in known[key]:
            kept[key] = value
        else:
            ignored.append(f"{key}={value}")
    return kept, ignored


def describe(values: dict[str, list[str]]) -> str:
    if not values:
        return ""
    parts = [
        f"{k}: " + ", ".join(json.dumps(v, ensure_ascii=False) for v in vs)
        for k, vs in values.items()
    ]
    return (
        " Para restringir a busca, passe `filtros` com campo e valor exatos, só quando a conversa"
        " já disser qual é. Campos e valores: " + "; ".join(parts) + "."
    )
