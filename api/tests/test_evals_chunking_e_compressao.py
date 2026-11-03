"""Evals do corte por base e da compressão do resultado de tool (ADR-0029).

Sem banco e sem rede. Errar o corte por títulos junta seções diferentes num trecho ou
separa o título do texto dele, e a busca devolve o pedaço errado. Errar a compressão
manda ao modelo o resultado inteiro, ou some com o custo do resumo.
"""

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pytest
from agno.agent import Agent
from agno.compression.manager import CompressionManager
from agno.knowledge.chunking.document import DocumentChunking
from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.document.base import Document
from agno.metrics import MessageMetrics
from agno.models.response import ModelResponse
from agno.run.base import RunStatus
from pydantic import ValidationError

from app.agents.replay import ReplayModel
from app.knowledge.chunking import HeadingChunking, overlap_for, strategy_for
from app.knowledge.ingest import read_documents
from app.schemas.knowledge_base import ChunkingSettings, KnowledgeBaseUpdate, overlap_problem
from app.settings import get_settings
from tests.fake_models import FixedReplyModel


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


MANUAL = (
    "Manual de atendimento da loja.\n\n"
    "# Troca\nTrinta dias corridos.\n\n"
    "## Troca em loja física\nCom a nota fiscal.\n\n"
    "# Reembolso\nAté cinco dias úteis no cartão de origem.\n\n"
    "# Senha\nExpira em noventa dias."
)


def _cut(level: int, text: str = MANUAL, size: int = 2000) -> list[str]:
    chunks = HeadingChunking(size, size // 10, level).chunk(Document(name="manual", content=text))
    return [c.content for c in chunks]


# --- corte por títulos ---


def test_criterio_de_aceite_tres_secoes_tres_trechos_com_o_titulo() -> None:
    text = "# Férias\nTrinta dias.\n\n# Reembolso\nCinco dias úteis.\n\n# Senha\nNoventa dias."
    assert [c.split("\n", 1)[0] for c in _cut(1, text)] == ["# Férias", "# Reembolso", "# Senha"]


def test_nivel_do_titulo_decide_onde_abre_trecho() -> None:
    # nível 1: a subseção fica dentro da seção de cima
    level1 = _cut(1)
    assert len(level1) == 4
    assert level1[0] == "Manual de atendimento da loja."
    assert "## Troca em loja física" in level1[1] and level1[1].startswith("# Troca")
    # nível 2: a subseção vira trecho próprio
    level2 = _cut(2)
    assert len(level2) == 5
    assert level2[2].startswith("## Troca em loja física")


def test_secao_grande_e_cortada_e_cada_pedaco_leva_o_titulo() -> None:
    long = "# Política de troca\n" + "\n".join(
        f"Regra {i}: vale para o item {i}." for i in range(60)
    )
    pieces = _cut(1, long, size=300)
    assert len(pieces) > 1
    assert all(p.startswith("# Política de troca") for p in pieces)
    assert "Regra 59" in pieces[-1]


def test_texto_sem_titulo_segue_a_recursiva() -> None:
    assert _cut(1, "Só um parágrafo, sem título nenhum.") == ["Só um parágrafo, sem título nenhum."]
    long = "Frase sem título. " * 100
    assert len(_cut(1, long, size=300)) > 1


def test_trechos_numerados_com_metadado_da_origem() -> None:
    doc = Document(name="manual", content=MANUAL, meta_data={"content_id": "c1"})
    chunks = HeadingChunking(2000, 200, 1).chunk(doc)
    assert [c.meta_data["chunk"] for c in chunks] == [1, 2, 3, 4]
    assert all(c.meta_data["content_id"] == "c1" for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


# --- estratégia e sobreposição ---


@pytest.mark.parametrize(
    ("strategy", "cls"),
    [
        ("recursive", RecursiveChunking),
        ("headings", HeadingChunking),
        ("paragraphs", DocumentChunking),
        ("fixed", FixedSizeChunking),
    ],
)
def test_estrategia_vira_o_chunker_certo(strategy: str, cls: type) -> None:
    assert isinstance(strategy_for(1000, ChunkingSettings(strategy=strategy)), cls)  # type: ignore[arg-type]


def test_sobreposicao_padrao_e_o_corte_de_antes_da_fase() -> None:
    # base antiga, com chunking vazio: recursiva com 10%, como antes do ADR-0029
    old = ChunkingSettings.model_validate({})
    chunker = strategy_for(2000, old)
    assert isinstance(chunker, RecursiveChunking) and chunker.overlap == 200
    assert overlap_for(2000, ChunkingSettings(overlap=0)) == 0


def test_sobreposicao_acima_de_30_por_cento_recusada() -> None:
    assert overlap_problem(1000, ChunkingSettings(overlap=300)) is None
    assert overlap_problem(1000, ChunkingSettings(overlap=301)) is not None
    with pytest.raises(ValidationError, match="30%"):
        KnowledgeBaseUpdate(name="x", chunk_size=1000, chunking=ChunkingSettings(overlap=400))
    with pytest.raises(ValidationError):
        ChunkingSettings(heading_level=4)


def test_leitura_de_arquivo_usa_o_corte_da_base() -> None:
    data = MANUAL.encode()
    by_heading = read_documents("manual", "md", data, 2000, ChunkingSettings(strategy="headings"))
    plain = read_documents("manual", "md", data, 2000)
    assert len(by_heading) == 5
    assert len(plain) == 1


# --- compressão do resultado de tool ---

BIG_RESULT = "pedido 123: enviado, valor R$ 210. " + "log de rastreio sem importância. " * 700


@dataclass
class SeesToolResult(ReplayModel):
    """Pede a tool uma vez e depois guarda o que chegou do resultado dela."""

    seen: list[str] = field(default_factory=list)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        messages = list(kwargs.get("messages") or (args[0] if args else []))
        tools = [m for m in messages if getattr(m, "role", None) == "tool"]
        if tools:
            self.seen = [str(m.get_content(use_compressed_content=True)) for m in tools]
            return ModelResponse(role="assistant", content="pedido 123 enviado")
        return ModelResponse(
            role="assistant",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "rastrear_pedido", "arguments": "{}"},
                }
            ],
        )


@dataclass
class Summarizer(FixedReplyModel):
    """Modelo da compressão: resumo fixo com o consumo medido."""

    input_tokens: int = 0
    prompts: list[str] = field(default_factory=list)

    def _respond(self) -> ModelResponse:
        usage = MessageMetrics(
            input_tokens=self.input_tokens,
            output_tokens=self.tokens,
            total_tokens=self.input_tokens + self.tokens,
        )
        return ModelResponse(role="assistant", content=self.reply, response_usage=usage)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        messages = list(kwargs.get("messages") or (args[0] if args else []))
        self.prompts.append(str(messages[-1].content))
        return self._respond()


def rastrear_pedido() -> str:
    """Rastreia o pedido do cliente."""
    return BIG_RESULT


async def test_resultado_grande_chega_comprimido_e_o_resumo_entra_no_custo() -> None:
    from app.pricing import estimate_cost, run_cost

    main = SeesToolResult(id="claude-sonnet-4-6")
    summarizer = Summarizer(
        id="claude-haiku-4-5", reply="pedido 123 enviado, R$ 210", tokens=20, input_tokens=5000
    )
    manager = CompressionManager(
        model=summarizer, compress_tool_results=True, compress_tool_results_limit=1
    )
    out = await Agent(model=main, tools=[rastrear_pedido], compression_manager=manager).arun(
        "onde está o pedido 123?"
    )
    assert out.status == RunStatus.completed
    # o modelo principal recebeu o resumo, não os 20 mil caracteres
    assert main.seen == ["pedido 123 enviado, R$ 210"]
    assert len(BIG_RESULT) > 20_000
    assert "pedido 123" in summarizer.prompts[0]
    assert out.metrics is not None and out.metrics.details is not None
    assert "compression_model" in out.metrics.details
    assert run_cost(out.metrics, "claude-sonnet-4-6") >= estimate_cost(  # type: ignore[operator]
        "claude-haiku-4-5", 5000, 20
    )


async def test_sem_compressao_o_resultado_chega_inteiro() -> None:
    main = SeesToolResult(id="claude-sonnet-4-6")
    out = await Agent(model=main, tools=[rastrear_pedido]).arun("onde está o pedido 123?")
    assert out.status == RunStatus.completed
    assert main.seen == [BIG_RESULT]


async def test_abaixo_do_gatilho_nada_e_comprimido() -> None:
    main = SeesToolResult(id="claude-sonnet-4-6")
    summarizer = Summarizer(id="claude-haiku-4-5", reply="resumo", tokens=5)
    manager = CompressionManager(
        model=summarizer, compress_tool_results=True, compress_tool_results_limit=3
    )
    await Agent(model=main, tools=[rastrear_pedido], compression_manager=manager).arun("pedido?")
    assert main.seen == [BIG_RESULT]
    assert summarizer.prompts == []


def test_titulo_comprido_nao_se_repete_nos_pedacos() -> None:
    # achado da auditoria da Fase 33: título numa linha só repetido em cada pedaço
    text = "# " + "x" * 40_000
    chunks = HeadingChunking(200, 20, 1).chunk(Document(name="d", content=text))
    assert max(len(c.content) for c in chunks) <= 200
    assert sum(len(c.content) for c in chunks) < len(text) * 2
    # título curto continua no início de cada pedaço
    section = "# Troca\n" + "Regra de troca sem fim. " * 100
    pieces = [
        c.content for c in HeadingChunking(300, 30, 1).chunk(Document(name="d", content=section))
    ]
    assert len(pieces) > 1 and all(p.startswith("# Troca") for p in pieces)
