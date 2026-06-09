from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.memory import MemoryService
from service.db import Base
from service.repositories.memories import MemoryRepository


def make_service():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    return MemoryService(MemoryRepository(db))


def test_graph_bfs_excludes_forgotten_and_merged():
    service = make_service()
    candidates = [
        service.extract_candidates(f"我喜欢 memory {i}。", source_kind="message", source_ref=str(i))[0]
        for i in range(4)
    ]
    memories = [service.confirm(c.id) for c in candidates]
    a, b, c, d = memories

    service.create_relation(a.id, b.id, relation_type="related_to")
    service.create_relation(b.id, c.id, relation_type="related_to")
    service.create_relation(c.id, d.id, relation_type="related_to")

    service.forget(c.id)

    graph = service.build_memory_graph(a.id, depth=3)
    assert {n.id for n in graph.nodes} == {a.id, b.id}
    assert len(graph.edges) == 1


def test_graph_bfs_respects_depth():
    service = make_service()
    candidates = [
        service.extract_candidates(f"我喜欢 memory {i}。", source_kind="message", source_ref=str(i))[0]
        for i in range(3)
    ]
    memories = [service.confirm(c.id) for c in candidates]
    a, b, c = memories

    service.create_relation(a.id, b.id, relation_type="related_to")
    service.create_relation(b.id, c.id, relation_type="related_to")

    depth1 = service.build_memory_graph(a.id, depth=1)
    depth2 = service.build_memory_graph(a.id, depth=2)

    assert {n.id for n in depth1.nodes} == {a.id, b.id}
    assert {n.id for n in depth2.nodes} == {a.id, b.id, c.id}


def test_graph_returns_empty_for_isolated_memory():
    service = make_service()
    candidate = service.extract_candidates("我喜欢 lonely。", source_kind="message", source_ref="1")[0]
    memory = service.confirm(candidate.id)

    graph = service.build_memory_graph(memory.id)

    assert graph.center_memory_id == memory.id
    assert len(graph.nodes) == 1
    assert graph.edges == []
