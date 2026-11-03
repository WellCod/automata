"""Corte do conteúdo da base em trechos (ADR-0029).

A estratégia vem da base; vazia, vale a recursiva com 10% de sobreposição, o corte de
antes da Fase 31. O corte por títulos é próprio: o MarkdownChunking do Agno exige o
`unstructured`.
"""

import re
from typing import Any

from agno.knowledge.chunking.document import DocumentChunking
from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.chunking.strategy import ChunkingStrategy
from agno.knowledge.document.base import Document

from app.schemas.knowledge_base import ChunkingSettings


def overlap_for(chunk_size: int, settings: ChunkingSettings) -> int:
    return chunk_size // 10 if settings.overlap is None else settings.overlap


class HeadingChunking(ChunkingStrategy):
    """Um trecho por seção de markdown, até o nível de título escolhido.

    A seção maior que o trecho é cortada pela recursiva, e cada pedaço leva o título no
    início. Texto sem título segue a recursiva.
    """

    def __init__(self, chunk_size: int, overlap: int, level: int) -> None:
        self.chunk_size = chunk_size
        self.level = level
        self._fallback = RecursiveChunking(chunk_size=chunk_size, overlap=overlap)
        self._heading = re.compile(rf"^#{{1,{level}}}[ \t]+\S.*$", re.MULTILINE)

    def sections(self, text: str) -> list[tuple[str | None, str]]:
        starts = [m.start() for m in self._heading.finditer(text)]
        if not starts:
            return [(None, text)]
        out: list[tuple[str | None, str]] = []
        if text[: starts[0]].strip():
            out.append((None, text[: starts[0]]))
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            section = text[start:end]
            out.append((section.split("\n", 1)[0].strip(), section))
        return out

    def chunk(self, document: Document) -> list[Document]:
        chunks: list[Document] = []
        for title, section in self.sections(document.content or ""):
            body = section.strip()
            if not body:
                continue
            pieces = [body]
            if len(body) > self.chunk_size:
                pieces = [
                    p.content
                    for p in self._fallback.chunk(Document(name=document.name, content=body))
                ]
                if title:
                    pieces = [p if p.startswith(title) else f"{title}\n{p}" for p in pieces]
            for piece in pieces:
                number = len(chunks) + 1
                meta: dict[str, Any] = {
                    **(document.meta_data or {}),
                    "chunk": number,
                    "chunk_size": len(piece),
                }
                chunks.append(
                    Document(
                        id=self._generate_chunk_id(document, number, piece),
                        name=document.name,
                        meta_data=meta,
                        content=piece,
                    )
                )
        return chunks


def strategy_for(chunk_size: int, settings: ChunkingSettings) -> ChunkingStrategy:
    overlap = overlap_for(chunk_size, settings)
    if settings.strategy == "headings":
        return HeadingChunking(chunk_size, overlap, settings.heading_level)
    if settings.strategy == "paragraphs":
        return DocumentChunking(chunk_size=chunk_size, overlap=overlap)
    if settings.strategy == "fixed":
        return FixedSizeChunking(chunk_size=chunk_size, overlap=overlap)
    return RecursiveChunking(chunk_size=chunk_size, overlap=overlap)
