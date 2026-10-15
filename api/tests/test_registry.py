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
    published = PublishedAgents(entries, lambda i: FakeFactory(str(i)), load_ids=lambda: ids)

    assert published.sync() == 1
    ids.append(b)
    assert published.sync() == 1
    assert published.sync() == 0
    assert [e.id for e in entries] == [str(a), str(b)]  # type: ignore[attr-defined]


def test_lista_e_mutada_no_lugar() -> None:
    entries: list[object] = []
    published = PublishedAgents(
        entries, lambda i: FakeFactory(str(i)), load_ids=lambda: [uuid.uuid4()]
    )
    published.sync()
    assert published.entries is entries
    assert len(entries) == 1


def test_ttl_controla_staleness() -> None:
    published = PublishedAgents([], lambda i: FakeFactory(str(i)), ttl_seconds=60, load_ids=list)
    assert published.is_stale()
    published.sync()
    assert not published.is_stale()


def test_falha_no_banco_nao_derruba() -> None:
    def boom() -> list[uuid.UUID]:
        raise RuntimeError("db fora")

    published = PublishedAgents([], lambda i: FakeFactory(str(i)), load_ids=boom)
    assert published.sync() == 0
