from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from service.config import get_settings
from service.core.elasticsearch_projection import ElasticsearchProjection
from service.core.embeddings import HashEmbeddingProvider
from service.core.knowledge import KnowledgeService
from service.models import SourceChunk
from service.repositories.agent import AgentRepository
from service.repositories.chunks import ChunkRepository
from service.schemas import ChunkRead, RetrievalMode, RetrievalSource

RetrievalBackend = Literal["local", "auto", "elasticsearch"]
RerankerHook = Callable[[str, list[ChunkRead], Any], list[ChunkRead]]


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: int
    score: float = 0.0


@dataclass(frozen=True)
class RetrievalScope:
    user_id: int | None = None
    knowledge_base_id: int | None = None


def rrf_fuse(
    bm25_hits: list[RetrievalHit],
    vector_hits: list[RetrievalHit],
    k: int,
    bm25_weight: float,
    vector_weight: float,
) -> list[RetrievalHit]:
    scores: dict[int, float] = {}
    first_seen: dict[int, int] = {}
    sequence = 0
    for weight, hits in ((bm25_weight, bm25_hits), (vector_weight, vector_hits)):
        for rank, hit in enumerate(hits, start=1):
            if hit.chunk_id not in first_seen:
                first_seen[hit.chunk_id] = sequence
                sequence += 1
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + (weight / (k + rank))
    return [
        RetrievalHit(chunk_id=chunk_id, score=score)
        for chunk_id, score in sorted(scores.items(), key=lambda item: (-item[1], first_seen[item[0]]))
    ]


class RetrievalService:
    def __init__(
        self,
        knowledge: KnowledgeService,
        chunks: ChunkRepository,
        *,
        projection: ElasticsearchProjection | None = None,
        embeddings: HashEmbeddingProvider | None = None,
        agent_repository: AgentRepository | None = None,
        reranker_hook: RerankerHook | None = None,
    ):
        self.knowledge = knowledge
        self.chunks = chunks
        self.projection = projection or ElasticsearchProjection()
        self.embeddings = embeddings or knowledge.embeddings
        self.agent_repository = agent_repository
        self.reranker_hook = reranker_hook

    @property
    def scope(self) -> RetrievalScope:
        return RetrievalScope(user_id=self.chunks.user_id, knowledge_base_id=self.chunks.knowledge_base_id)

    def search(self, query: str, limit: int = 5, backend: RetrievalBackend | None = None) -> list[ChunkRead]:
        selected_backend = backend or get_settings().retrieval_backend
        if selected_backend == "local":
            return self._local(query, limit, retrieval_source="local")
        if selected_backend == "auto":
            try:
                results = self._elasticsearch_candidates(query, limit)
            except Exception:
                return self._local(query, limit, retrieval_source="local_fallback")
            if not results:
                return self._local(query, limit, retrieval_source="local_fallback")
            return self._maybe_rerank(query, results)[:limit]
        if selected_backend == "elasticsearch":
            results = self._elasticsearch_candidates(query, limit)
            return self._maybe_rerank(query, results)[:limit]
        raise ValueError(f"unsupported retrieval backend: {selected_backend}")

    def _local(self, query: str, limit: int, retrieval_source: RetrievalSource) -> list[ChunkRead]:
        return [
            result.model_copy(update={"retrieval_mode": "local", "retrieval_source": retrieval_source})
            for result in self.knowledge.search(query, limit=limit)
        ]

    def _elasticsearch_candidates(self, query: str, limit: int) -> list[ChunkRead]:
        settings = get_settings()
        scope = self.scope
        bm25_hits = [
            _hit_from_elasticsearch(hit)
            for hit in self.projection.search_bm25(query, user_id=scope.user_id, knowledge_base_id=scope.knowledge_base_id, limit=limit)
        ]
        vector = self.embeddings.embed(query)
        vector_hits = [
            _hit_from_elasticsearch(hit)
            for hit in self.projection.search_vector(vector, user_id=scope.user_id, knowledge_base_id=scope.knowledge_base_id, limit=limit)
        ]
        fused = rrf_fuse(
            bm25_hits,
            vector_hits,
            k=60,
            bm25_weight=settings.retrieval_bm25_weight,
            vector_weight=settings.retrieval_vector_weight,
        )
        fused_by_id = {hit.chunk_id: hit for hit in fused}
        chunk_ids = [hit.chunk_id for hit in fused]
        rows = self.chunks.list_by_ids(chunk_ids)
        return [self._chunk_read(row, fused_by_id[row.id].score) for row in rows]

    def _chunk_read(self, chunk: SourceChunk, score: float) -> ChunkRead:
        return ChunkRead(
            id=chunk.id,
            source_id=chunk.source_id,
            source_title=chunk.source.title,
            text=chunk.text,
            score=score,
            retrieval_mode="es_hybrid",
            retrieval_source="elasticsearch",
        )

    def _maybe_rerank(self, query: str, candidates: list[ChunkRead]) -> list[ChunkRead]:
        if not candidates or self.agent_repository is None or self.reranker_hook is None:
            return candidates
        profile = self.agent_repository.active_reranker_profile()
        if profile is None or not profile.is_active or not profile.base_url:
            return candidates
        scoped_candidates = candidates[: profile.top_n]
        try:
            reranked = self.reranker_hook(query, scoped_candidates, profile)
        except Exception:
            return candidates
        allowed_ids = {candidate.id for candidate in scoped_candidates}
        scoped_reranked = [candidate for candidate in reranked if candidate.id in allowed_ids]
        return scoped_reranked + [candidate for candidate in candidates if candidate.id not in {item.id for item in scoped_reranked}]


def _hit_from_elasticsearch(hit: dict[str, Any]) -> RetrievalHit:
    source = hit.get("_source") if isinstance(hit, dict) else None
    if not isinstance(source, dict) or "chunk_id" not in source:
        raise ValueError("Elasticsearch hit missing _source.chunk_id")
    return RetrievalHit(chunk_id=int(source["chunk_id"]), score=float(hit.get("_score") or 0.0))
