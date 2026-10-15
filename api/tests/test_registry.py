import uuid
from dataclasses import dataclass

from app.agents.registry import PublishedAgents


@dataclass
class FakeFactory:
    id: str


def test_sync_registra_so_os_novos() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    ids = [a]
    entries: list[object] = []
    published = PublishedAgents(
        entries, lambda i: FakeFactory(str(i)), load=lambda: [(i, "agent") for i in ids]
    )

    assert published.sync() == 1
    ids.append(b)
    assert published.sync() == 1
    assert published.sync() == 0
    assert [e.id for e in entries] == [str(a), str(b)]  # type: ignore[attr-defined]


def test_lista_e_mutada_no_lugar() -> None:
    entries: list[object] = []
    published = PublishedAgents(
        entries, lambda i: FakeFactory(str(i)), load=lambda: [(uuid.uuid4(), "agent")]
    )
    published.sync()
    assert published.entries is entries
    assert len(entries) == 1


def test_ttl_controla_staleness() -> None:
    published = PublishedAgents([], lambda i: FakeFactory(str(i)), ttl_seconds=60, load=list)
    assert published.is_stale()
    published.sync()
    assert not published.is_stale()


def test_falha_no_banco_nao_derruba() -> None:
    def boom() -> list[tuple[uuid.UUID, str]]:
        raise RuntimeError("db fora")

    published = PublishedAgents([], lambda i: FakeFactory(str(i)), load=boom)
    assert published.sync() == 0


def test_times_vao_para_a_lista_de_times() -> None:
    agente, time = uuid.uuid4(), uuid.uuid4()
    entries: list[object] = []
    teams: list[object] = []
    published = PublishedAgents(
        entries,
        lambda i: FakeFactory(f"a-{i}"),
        teams=teams,
        make_team_factory=lambda i: FakeFactory(str(i)),
        load=lambda: [(agente, "agent"), (time, "team")],
    )
    published.sync()
    assert [e.id for e in entries] == [f"a-{agente}"]  # type: ignore[attr-defined]
    assert [t.id for t in teams] == [str(time)]  # type: ignore[attr-defined]


def test_falha_no_banco_espera_o_ttl_para_tentar_de_novo() -> None:
    chamadas = 0

    def boom() -> list[tuple[uuid.UUID, str]]:
        nonlocal chamadas
        chamadas += 1
        raise RuntimeError("db fora")

    published = PublishedAgents([], lambda i: FakeFactory(str(i)), ttl_seconds=60, load=boom)
    published.sync()
    assert not published.is_stale()
    assert chamadas == 1
