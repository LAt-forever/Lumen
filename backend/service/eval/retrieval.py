from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from service.core.chat import ChatOrchestrator
from service.core.global_search import GlobalSearchService
from service.core.knowledge import KnowledgeService
from service.core.memory import MemoryService
from service.db import SessionLocal, init_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChatRequest, SourceCreate

CASES_PATH = Path(__file__).with_name("retrieval_cases.json")


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    query: str
    expected_result_type: str | None
    expected_marker: str
    description: str


@dataclass(frozen=True)
class RetrievalCaseResult:
    id: str
    passed: bool
    query: str
    expected_result_type: str | None
    top_result_type: str | None
    top_title: str | None
    details: str


def load_cases(path: Path = CASES_PATH) -> list[RetrievalCase]:
    return [RetrievalCase(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def seed_retrieval_evaluation_corpus(db: Session) -> None:
    sources = SourceRepository(db)
    chunks = ChunkRepository(db)
    memories = MemoryRepository(db)
    conversations = ConversationRepository(db)
    organization = OrganizationRepository(db)
    knowledge = KnowledgeService(sources, chunks)
    memory_service = MemoryService(memories)
    chat = ChatOrchestrator(conversations, knowledge, memory_service)

    source = sources.create(
        SourceCreate(
            title="Phase15 工作日报",
            source_type="note",
            content="时间 | 2026年6月9日 记录 | Phase15 完成全局搜索、标签收藏和状态面板设计。",
        )
    )
    knowledge.index_source(source.id)

    for message in (
        "我正在做 Phase15 组织和全局搜索项目。",
        "我喜欢 Phase15 搜索结果显示中文匹配原因。",
    ):
        memory_service.extract_candidates(message, source_kind="evaluation", source_ref=message[:20])
        candidate = memories.pending_candidates()[0]
        memories.confirm(candidate.id, text=candidate.text, memory_type=candidate.memory_type)

    response = chat.ask(ChatRequest(message="Phase15 收藏回答应该能在以后搜索回来。"))
    tag = organization.create_tag("Phase15", "#2563eb")
    organization.assign_tag(tag.id, "source", source.id)
    organization.favorite("message", response.message_id)


def run_retrieval_evaluation(db: Session, cases: list[RetrievalCase] | None = None) -> list[RetrievalCaseResult]:
    cases = cases or load_cases()
    search = GlobalSearchService(
        SourceRepository(db),
        ChunkRepository(db),
        MemoryRepository(db),
        ConversationRepository(db),
        OrganizationRepository(db),
    )
    results: list[RetrievalCaseResult] = []
    for case in cases:
        search_results = search.search(case.query, limit=3)
        top = search_results[0] if search_results else None
        serialized = json.dumps([result.model_dump(mode="json") for result in search_results], ensure_ascii=False)
        if case.expected_result_type is None:
            passed = top is None
        else:
            passed = any(result.result_type == case.expected_result_type for result in search_results)
            if case.expected_marker:
                passed = passed and case.expected_marker in serialized
        results.append(
            RetrievalCaseResult(
                id=case.id,
                passed=passed,
                query=case.query,
                expected_result_type=case.expected_result_type,
                top_result_type=top.result_type if top else None,
                top_title=top.title if top else None,
                details=case.description,
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Lumen retrieval quality evaluation")
    parser.add_argument("--seed", action="store_true", help="Seed the evaluation corpus before running cases")
    args = parser.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        if args.seed:
            seed_retrieval_evaluation_corpus(db)
        results = run_retrieval_evaluation(db)
    print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
