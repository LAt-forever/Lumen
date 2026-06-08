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


def test_edit_confirmed_memory_updates_text_type_and_status():
    service = make_service()
    candidate = service.extract_candidates("我喜欢引用清楚的回答。", source_kind="message", source_ref="1")[0]
    memory = service.confirm(candidate.id)

    updated = service.edit(memory.id, text="用户偏好带清晰引用的回答。", memory_type="preference")

    assert updated.id == memory.id
    assert updated.text == "用户偏好带清晰引用的回答。"
    assert updated.memory_type == "preference"
    assert updated.status == "edited"


def test_forget_confirmed_memory_removes_it_from_search():
    service = make_service()
    candidate = service.extract_candidates("我喜欢引用清楚的回答。", source_kind="message", source_ref="1")[0]
    memory = service.confirm(candidate.id)

    forgotten = service.forget(memory.id)

    assert forgotten.status == "forgotten"
    assert service.search("引用清楚") == []


def test_merge_memory_combines_text_and_hides_source():
    service = make_service()
    first = service.extract_candidates("我正在做 Lumen 这个个人 AI 知识库项目。", source_kind="message", source_ref="1")[0]
    second = service.extract_candidates("我喜欢用中文记录项目目标。", source_kind="message", source_ref="2")[0]
    target = service.confirm(first.id)
    source = service.confirm(second.id)

    merged = service.merge(source.id, target_memory_id=target.id)

    assert merged.id == target.id
    assert "Lumen" in merged.text
    assert "中文记录项目目标" in merged.text
    assert merged.status == "edited"
    assert [memory.id for memory in service.memories.active_memories()] == [target.id]


def test_search_blank_query_returns_no_memories():
    service = make_service()
    candidate = service.extract_candidates("我喜欢引用清楚的回答。", source_kind="message", source_ref="1")[0]
    service.confirm(candidate.id)

    assert service.search("   ") == []


def test_search_finds_mixed_chinese_english_follow_up_without_spaces():
    service = make_service()
    candidate = service.extract_candidates("我正在做 Lumen 这个个人 AI 知识库项目。", source_kind="message", source_ref="1")[0]
    memory = service.confirm(candidate.id)

    results = service.search("Lumen后续怎么做？")

    assert [result.id for result in results] == [memory.id]


def test_search_does_not_return_unrelated_memories():
    service = make_service()
    candidate = service.extract_candidates("我正在做 Lumen 这个个人 AI 知识库项目。", source_kind="message", source_ref="1")[0]
    service.confirm(candidate.id)

    assert service.search("晚饭吃什么？") == []
