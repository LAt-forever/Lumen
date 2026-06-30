from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.core.retrieval import RetrievalBackend, RetrievalService
from service.db import SessionLocal, init_db
from service.models import Source, User
from service.repositories.chunks import ChunkRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.sources import SourceRepository
from service.schemas import KnowledgeBaseCreate, SourceCreate

CASES_PATH = Path(__file__).with_name("retrieval_cases.json")
EVAL_USER_ID = 1
DEFAULT_KB_KEY = "default"
RESEARCH_KB_KEY = "research"
RESEARCH_KB_NAME = "Phase 2 Research"


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    query: str
    backend: RetrievalBackend
    knowledge_base_key: str
    expected_source_title: str | None
    expected_marker: str
    expected_retrieval_source: str | None
    description: str


@dataclass(frozen=True)
class RetrievalCaseResult:
    id: str
    passed: bool
    query: str
    backend: RetrievalBackend
    expected_knowledge_base_id: int | None
    actual_knowledge_base_id: int | None
    expected_source_title: str | None
    top_title: str | None
    details: str


def load_cases(path: Path = CASES_PATH) -> list[RetrievalCase]:
    return [RetrievalCase(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def seed_retrieval_evaluation_corpus(db: Session) -> None:
    _ensure_evaluation_user(db)
    knowledge_bases = KnowledgeBaseRepository(db, user_id=EVAL_USER_ID)
    default_kb = knowledge_bases.ensure_default()
    research_kb = _ensure_knowledge_base(knowledge_bases, RESEARCH_KB_NAME)

    _index_eval_source(
        db,
        default_kb.id,
        title="Default KB retrieval note",
        content=(
            "DefaultOnlySignal belongs to the default knowledge base. "
            "CometExactBM25Token should be retrieved by exact BM25 keyword matching. "
            "Durable recall means the assistant can preserve context and cite grounded source chunks."
        ),
    )
    _index_eval_source(
        db,
        research_kb.id,
        title="Research KB isolation note",
        content=(
            "DefaultOnlySignal appears here as a decoy in a second knowledge base. "
            "The retrieval evaluation must not accept this source when the expected scope is default."
        ),
    )


def run_retrieval_evaluation(db: Session, cases: list[RetrievalCase] | None = None) -> list[RetrievalCaseResult]:
    cases = cases or load_cases()
    knowledge_base_ids = _evaluation_knowledge_base_ids(db)
    results: list[RetrievalCaseResult] = []
    for case in cases:
        expected_kb_id = knowledge_base_ids.get(case.knowledge_base_key)
        if expected_kb_id is None:
            raise ValueError(f"unknown evaluation knowledge base key: {case.knowledge_base_key}")

        chunks = ChunkRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=expected_kb_id)
        knowledge = KnowledgeService(
            SourceRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=expected_kb_id),
            chunks,
            indexing_runs=IndexingRunRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=expected_kb_id),
        )
        retrieval = RetrievalService(
            knowledge=knowledge,
            chunks=chunks,
            projection=EvaluationProjection(chunks),
            embeddings=EvaluationEmbeddingProvider(),
        )
        search_results = retrieval.search(case.query, limit=3, backend=case.backend)
        top = search_results[0] if search_results else None
        actual_kb_id = _source_knowledge_base_id(db, top.source_id) if top is not None else None
        serialized = json.dumps([result.model_dump(mode="json") for result in search_results], ensure_ascii=False)

        if case.expected_source_title is None:
            passed = top is None
        else:
            passed = (
                any(result.source_title == case.expected_source_title for result in search_results)
                and actual_kb_id == expected_kb_id
            )
            if case.expected_marker:
                passed = passed and case.expected_marker in serialized
            if case.expected_retrieval_source:
                passed = passed and any(
                    result.retrieval_source == case.expected_retrieval_source for result in search_results
                )

        results.append(
            RetrievalCaseResult(
                id=case.id,
                passed=passed,
                query=case.query,
                backend=case.backend,
                expected_knowledge_base_id=expected_kb_id,
                actual_knowledge_base_id=actual_kb_id,
                expected_source_title=case.expected_source_title,
                top_title=top.source_title if top else None,
                details=case.description,
            )
        )
    return results


class EvaluationProjection:
    def __init__(self, chunks: ChunkRepository):
        self.chunks = chunks

    def search_bm25(
        self,
        query: str,
        user_id: int | None,
        knowledge_base_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if "ZqxvNoMatchToken" in query:
            raise RuntimeError("simulated projection outage for weak-evidence fallback")
        if "CometExactBM25Token" not in query:
            return []
        return self._hits("CometExactBM25Token", limit)

    def search_vector(
        self,
        vector: list[float],
        user_id: int | None,
        knowledge_base_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not vector or vector[0] != 1.0:
            return []
        return self._hits("Durable recall means", limit)

    def _hits(self, marker: str, limit: int) -> list[dict[str, Any]]:
        hits = []
        for chunk in self.chunks.list_all():
            if marker.lower() in chunk.text.lower():
                hits.append({"_score": 1.0, "_source": {"chunk_id": str(chunk.id)}})
        return hits[:limit]


class EvaluationEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        if "durable recall" in text.lower():
            return [1.0]
        return [0.0]


def _ensure_knowledge_base(repository: KnowledgeBaseRepository, name: str):
    for knowledge_base in repository.list():
        if knowledge_base.name == name:
            return knowledge_base
    return repository.create(KnowledgeBaseCreate(name=name, description="Retrieval evaluation secondary scope"))


def _ensure_evaluation_user(db: Session) -> None:
    if db.get(User, EVAL_USER_ID) is not None:
        return
    db.add(
        User(
            id=EVAL_USER_ID,
            email="retrieval-eval@example.local",
            password_hash="retrieval-eval",
            is_admin=False,
        )
    )
    db.commit()


def _index_eval_source(db: Session, knowledge_base_id: int, *, title: str, content: str) -> None:
    sources = SourceRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=knowledge_base_id)
    chunks = ChunkRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=knowledge_base_id)
    knowledge = KnowledgeService(
        sources,
        chunks,
        indexing_runs=IndexingRunRepository(db, user_id=EVAL_USER_ID, knowledge_base_id=knowledge_base_id),
    )
    source = sources.create(SourceCreate(title=title, source_type="note", content=content))
    knowledge.index_source(source.id)


def _evaluation_knowledge_base_ids(db: Session) -> dict[str, int]:
    repository = KnowledgeBaseRepository(db, user_id=EVAL_USER_ID)
    default = repository.ensure_default()
    research = _ensure_knowledge_base(repository, RESEARCH_KB_NAME)
    return {DEFAULT_KB_KEY: default.id, RESEARCH_KB_KEY: research.id}


def _source_knowledge_base_id(db: Session, source_id: int) -> int | None:
    source = db.get(Source, source_id)
    return source.knowledge_base_id if source is not None else None


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
