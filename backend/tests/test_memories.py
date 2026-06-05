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


def test_extracts_project_memory_candidate():
    service = make_service()

    candidates = service.extract_candidates("我正在做 Lumen 这个个人 AI 知识库项目。", source_kind="message", source_ref="1")

    assert len(candidates) == 1
    assert candidates[0].memory_type == "project"
    assert "Lumen" in candidates[0].text


def test_confirm_candidate_creates_active_memory():
    service = make_service()
    candidate = service.extract_candidates("我喜欢引用清楚的回答。", source_kind="message", source_ref="1")[0]

    memory = service.confirm(candidate.id, text="用户喜欢引用清楚的回答。", memory_type="preference")

    assert memory.status == "active"
    assert memory.memory_type == "preference"
    assert memory.text == "用户喜欢引用清楚的回答。"
