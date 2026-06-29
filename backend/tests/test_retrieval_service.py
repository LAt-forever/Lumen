import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.core.knowledge import KnowledgeService
from service.core.retrieval import RetrievalHit, RetrievalService, rrf_fuse
from service.db import Base
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


class StaticEmbeddingProvider:
    dimensions = 3

    def embed(self, _text):
        return [0.1, 0.2, 0.3]


class FailingEmbeddingProvider:
    dimensions = 3

    def embed(self, _text):
        raise RuntimeError("embedding failed")


class FakeHybridProjection:
    def __init__(self):
        self.bm25_hits = []
        self.vector_hits = []
        self.calls = []

    def search_bm25(self, query, user_id, knowledge_base_id, limit):
        self.calls.append(("bm25", query, user_id, knowledge_base_id, limit))
        return self.bm25_hits

    def search_vector(self, vector, user_id, knowledge_base_id, limit):
        self.calls.append(("vector", vector, user_id, knowledge_base_id, limit))
        return self.vector_hits


class FailingProjection:
    def search_bm25(self, *_args, **_kwargs):
        raise RuntimeError("es is down")

    def search_vector(self, *_args, **_kwargs):
        raise AssertionError("vector search should not run after bm25 failure")


class VectorFailingProjection:
    def __init__(self, bm25_hits):
        self.bm25_hits = bm25_hits
        self.calls = []

    def search_bm25(self, query, user_id, knowledge_base_id, limit):
        self.calls.append(("bm25", query, user_id, knowledge_base_id, limit))
        return self.bm25_hits

    def search_vector(self, vector, user_id, knowledge_base_id, limit):
        self.calls.append(("vector", vector, user_id, knowledge_base_id, limit))
        raise RuntimeError("vector search failed")


class ExplodingProjection:
    def search_bm25(self, *_args, **_kwargs):
        raise AssertionError("ES backend should not be called")

    def search_vector(self, *_args, **_kwargs):
        raise AssertionError("ES backend should not be called")


class ActiveRerankerRepository:
    def active_reranker_profile(self):
        return type("RerankerProfile", (), {"is_active": True, "base_url": "http://reranker.example", "top_n": 10})()


def make_service(user_id=7, knowledge_base_id=11):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    sources = SourceRepository(db, user_id=user_id, knowledge_base_id=knowledge_base_id)
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=knowledge_base_id)
    knowledge = KnowledgeService(sources, chunks, embeddings=StaticEmbeddingProvider())
    return db, knowledge, chunks


def es_hit(chunk_id, score):
    return {"_score": score, "_source": {"chunk_id": str(chunk_id)}}


def indexed_chunk(knowledge, chunks, *, title="Scoped Lumen", content="Lumen hybrid retrieval should reload scoped chunks."):
    source = knowledge.sources.create(SourceCreate(title=title, source_type="note", content=content))
    knowledge.index_source(source.id)
    return chunks.list_all()[-1]


def test_rrf_fuse_orders_overlap_ahead_and_preserves_first_seen_ties():
    fused = rrf_fuse(
        bm25_hits=[RetrievalHit(chunk_id=1), RetrievalHit(chunk_id=2)],
        vector_hits=[RetrievalHit(chunk_id=2), RetrievalHit(chunk_id=3)],
        k=60,
        bm25_weight=1.0,
        vector_weight=1.0,
    )

    assert [hit.chunk_id for hit in fused] == [2, 1, 3]


def test_hybrid_retrieval_fuses_es_hits_and_reloads_chunks_through_postgres_scope():
    db, knowledge, chunks = make_service()
    scoped_source = knowledge.sources.create(
        SourceCreate(title="Scoped Lumen", source_type="note", content="Lumen hybrid retrieval should reload scoped chunks.")
    )
    cross_scope_source = SourceRepository(db, user_id=99, knowledge_base_id=11).create(
        SourceCreate(title="Other User", source_type="note", content="This chunk must not leak across users.")
    )
    knowledge.index_source(scoped_source.id)
    KnowledgeService(
        SourceRepository(db, user_id=99, knowledge_base_id=11),
        ChunkRepository(db, user_id=99, knowledge_base_id=11),
        embeddings=StaticEmbeddingProvider(),
    ).index_source(cross_scope_source.id)
    scoped_chunk = chunks.list_all()[0]
    cross_scope_chunk = ChunkRepository(db, user_id=99, knowledge_base_id=11).list_all()[0]
    projection = FakeHybridProjection()
    projection.bm25_hits = [es_hit(cross_scope_chunk.id, 20.0), es_hit(scoped_chunk.id, 9.0)]
    projection.vector_hits = [es_hit(scoped_chunk.id, 8.0)]
    retrieval = RetrievalService(knowledge=knowledge, chunks=chunks, projection=projection)

    results = retrieval.search("hybrid retrieval", backend="elasticsearch", limit=5)

    assert [result.id for result in results] == [scoped_chunk.id]
    assert results[0].retrieval_mode == "es_hybrid"
    assert results[0].retrieval_source == "elasticsearch"
    assert projection.calls == [
        ("bm25", "hybrid retrieval", 7, 11, 5),
        ("vector", [0.1, 0.2, 0.3], 7, 11, 5),
    ]


def test_auto_retrieval_keeps_es_results_when_reranker_fails():
    _db, knowledge, chunks = make_service()
    scoped_chunk = indexed_chunk(knowledge, chunks, title="ES Result", content="Hybrid retrieval should survive reranker outages.")
    projection = FakeHybridProjection()
    projection.bm25_hits = [es_hit(scoped_chunk.id, 9.0)]
    projection.vector_hits = [es_hit(scoped_chunk.id, 8.0)]

    def failing_reranker(_query, _candidates, _profile):
        raise RuntimeError("reranker is down")

    retrieval = RetrievalService(
        knowledge=knowledge,
        chunks=chunks,
        projection=projection,
        agent_repository=ActiveRerankerRepository(),
        reranker_hook=failing_reranker,
    )

    results = retrieval.search("hybrid retrieval", backend="auto", limit=5)

    assert [result.id for result in results] == [scoped_chunk.id]
    assert results[0].retrieval_mode == "es_hybrid"
    assert results[0].retrieval_source == "elasticsearch"


def test_reranker_keeps_only_scoped_candidates_in_reranked_order():
    _db, knowledge, chunks = make_service()
    first_chunk = indexed_chunk(knowledge, chunks, title="First Candidate", content="First scoped candidate for reranking.")
    second_chunk = indexed_chunk(knowledge, chunks, title="Second Candidate", content="Second scoped candidate for reranking.")
    projection = FakeHybridProjection()
    projection.bm25_hits = [es_hit(first_chunk.id, 9.0), es_hit(second_chunk.id, 8.0)]
    projection.vector_hits = [es_hit(first_chunk.id, 7.0), es_hit(second_chunk.id, 6.0)]

    def rerank_with_extra(_query, candidates, _profile):
        extra = candidates[0].model_copy(update={"id": 999_999, "source_id": 999_999, "source_title": "Out of scope"})
        return [candidates[1], extra, candidates[0]]

    retrieval = RetrievalService(
        knowledge=knowledge,
        chunks=chunks,
        projection=projection,
        agent_repository=ActiveRerankerRepository(),
        reranker_hook=rerank_with_extra,
    )

    results = retrieval.search("candidate reranking", backend="elasticsearch", limit=5)

    assert [result.id for result in results] == [second_chunk.id, first_chunk.id]
    assert {result.retrieval_source for result in results} == {"elasticsearch"}


def test_local_retrieval_does_not_call_elasticsearch_backend():
    _db, knowledge, chunks = make_service()
    indexed_chunk(knowledge, chunks, title="Local Only", content="Local retrieval should not call ES.")
    retrieval = RetrievalService(knowledge=knowledge, chunks=chunks, projection=ExplodingProjection())

    results = retrieval.search("local retrieval", backend="local", limit=5)

    assert results
    assert results[0].source_title == "Local Only"
    assert results[0].retrieval_mode == "local"
    assert results[0].retrieval_source == "local"


def test_auto_retrieval_falls_back_to_local_when_elasticsearch_fails():
    _db, knowledge, chunks = make_service()
    source = knowledge.sources.create(
        SourceCreate(title="Local fallback", source_type="note", content="Fallback retrieval still searches local chunks.")
    )
    knowledge.index_source(source.id)
    retrieval = RetrievalService(knowledge=knowledge, chunks=chunks, projection=FailingProjection())

    results = retrieval.search("fallback retrieval", backend="auto", limit=5)

    assert results
    assert results[0].source_title == "Local fallback"
    assert results[0].retrieval_mode == "local"
    assert results[0].retrieval_source == "local_fallback"


def test_auto_retrieval_falls_back_when_vector_search_fails_after_bm25_succeeds():
    _db, knowledge, chunks = make_service()
    scoped_chunk = indexed_chunk(
        knowledge,
        chunks,
        title="Vector Fallback",
        content="Vector failure after BM25 should fallback locally in auto.",
    )
    projection = VectorFailingProjection(bm25_hits=[es_hit(scoped_chunk.id, 9.0)])
    retrieval = RetrievalService(knowledge=knowledge, chunks=chunks, projection=projection)

    results = retrieval.search("vector failure", backend="auto", limit=5)

    assert results
    assert results[0].source_title == "Vector Fallback"
    assert results[0].retrieval_mode == "local"
    assert results[0].retrieval_source == "local_fallback"
    assert projection.calls == [
        ("bm25", "vector failure", 7, 11, 5),
        ("vector", [0.1, 0.2, 0.3], 7, 11, 5),
    ]


def test_elasticsearch_backend_raises_when_elasticsearch_fails():
    _db, knowledge, chunks = make_service()
    retrieval = RetrievalService(knowledge=knowledge, chunks=chunks, projection=FailingProjection())

    with pytest.raises(RuntimeError, match="es is down"):
        retrieval.search("fallback retrieval", backend="elasticsearch", limit=5)


def test_auto_retrieval_falls_back_when_embedding_fails():
    _db, knowledge, chunks = make_service()
    indexed_chunk(knowledge, chunks, title="Embedding Fallback", content="Embedding failure should fallback locally in auto.")
    projection = FakeHybridProjection()
    retrieval = RetrievalService(
        knowledge=knowledge,
        chunks=chunks,
        projection=projection,
        embeddings=FailingEmbeddingProvider(),
    )

    results = retrieval.search("embedding failure", backend="auto", limit=5)

    assert results
    assert results[0].source_title == "Embedding Fallback"
    assert results[0].retrieval_mode == "local"
    assert results[0].retrieval_source == "local_fallback"


def test_elasticsearch_retrieval_raises_when_embedding_fails():
    _db, knowledge, chunks = make_service()
    retrieval = RetrievalService(
        knowledge=knowledge,
        chunks=chunks,
        projection=FakeHybridProjection(),
        embeddings=FailingEmbeddingProvider(),
    )

    with pytest.raises(RuntimeError, match="embedding failed"):
        retrieval.search("embedding failure", backend="elasticsearch", limit=5)
