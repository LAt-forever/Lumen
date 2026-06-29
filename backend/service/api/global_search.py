from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.global_search import GlobalSearchService, SearchCandidate
from service.core.knowledge import KnowledgeService
from service.core.retrieval import RetrievalService
from service.db import get_db
from service.models import User
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import GlobalSearchResultRead

router = APIRouter(prefix="/api/global-search", tags=["global-search"])

_ALLOWED_TYPES = {"source_chunk", "source", "memory", "message"}


class RuntimeRetrieval:
    def __init__(self, retrieval: RetrievalService):
        self.retrieval = retrieval

    def search(self, query: str, limit: int = 5):
        return self.retrieval.search(query, limit=limit)


class RetrievalGlobalSearchService(GlobalSearchService):
    def __init__(self, *args, retrieval, **kwargs):
        super().__init__(*args, **kwargs)
        self.retrieval = retrieval
        self._retrieval_query = ""
        self._result_types: set[str] | None = None
        self._has_source_chunk_filters = False
        self._retrieval_metadata = {}

    def search(
        self,
        query: str,
        result_types: set[str] | None = None,
        tag: str | None = None,
        favorite: bool = False,
        limit: int = 20,
    ):
        self._retrieval_query = query
        self._result_types = result_types
        self._has_source_chunk_filters = bool(tag or favorite)
        results = super().search(query, result_types=result_types, tag=tag, favorite=favorite, limit=limit)
        return [
            result.model_copy(
                update={
                    "retrieval_mode": metadata[0],
                    "retrieval_source": metadata[1],
                }
            )
            if result.result_type == "source_chunk" and (metadata := self._retrieval_metadata.get(result.target_id))
            else result
            for result in results
        ]

    def _candidates(self) -> list[SearchCandidate]:
        self._retrieval_metadata = {}
        candidates: list[SearchCandidate] = []
        if self._includes_source_chunks():
            if self._has_source_chunk_filters:
                candidates.extend(self._chunk_candidate(chunk) for chunk in self.chunks.list_all())
            else:
                candidates.extend(
                    self._retrieval_chunk_candidate(chunk)
                    for chunk in self.retrieval.search(self._retrieval_query, 20)
                )
        for source in self.sources.list_all():
            candidates.append(self._source_candidate(source))
        for memory in self.memories.list_active_for_search():
            candidates.append(self._memory_candidate(memory))
        for message in self.conversations.list_messages_for_search():
            candidates.append(self._message_candidate(message))
        return candidates

    def _includes_source_chunks(self) -> bool:
        return self._result_types is None or "source_chunk" in self._result_types

    def _retrieval_chunk_candidate(self, chunk) -> SearchCandidate:
        row = self.chunks.list_by_ids([chunk.id])[0]
        self._retrieval_metadata[chunk.id] = (chunk.retrieval_mode, chunk.retrieval_source)
        return SearchCandidate(
            result_type="source_chunk",
            target_id=chunk.id,
            organization_type="source",
            organization_id=chunk.source_id,
            title=chunk.source_title,
            text=f"{chunk.source_title}\n{chunk.text}",
            created_at=row.created_at,
        )


def _parse_types(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    parsed: set[str] = set()
    for value in values:
        parsed.update(part.strip() for part in value.split(",") if part.strip())
    return {value for value in parsed if value in _ALLOWED_TYPES} or None


def _raise_kb_http(exc: ValueError) -> None:
    message = str(exc)
    status_code = 404 if "not found" in message else 400
    raise HTTPException(status_code=status_code, detail=message) from exc


def _active_knowledge_base_id(db: Session, user_id: int, knowledge_base_id: int | None) -> int:
    try:
        return KnowledgeBaseRepository(db, user_id=user_id).require_active(knowledge_base_id).id
    except ValueError as exc:
        _raise_kb_http(exc)


def _retrieval_service(db: Session, user_id: int, knowledge_base_id: int) -> RuntimeRetrieval:
    sources = SourceRepository(db, user_id=user_id, knowledge_base_id=knowledge_base_id)
    chunks = ChunkRepository(db, user_id=user_id, knowledge_base_id=knowledge_base_id)
    return RuntimeRetrieval(RetrievalService(KnowledgeService(sources, chunks), chunks))


@router.get("", response_model=list[GlobalSearchResultRead])
def global_search(
    q: str = Query(min_length=1),
    types: list[str] | None = Query(default=None),
    tag: str | None = None,
    favorite: bool = False,
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_knowledge_base_id = _active_knowledge_base_id(db, current_user.id, knowledge_base_id)
    service = RetrievalGlobalSearchService(
        SourceRepository(db, user_id=current_user.id, knowledge_base_id=active_knowledge_base_id),
        ChunkRepository(db, user_id=current_user.id, knowledge_base_id=active_knowledge_base_id),
        MemoryRepository(db, user_id=current_user.id),
        ConversationRepository(db, user_id=current_user.id),
        OrganizationRepository(db, user_id=current_user.id),
        retrieval=_retrieval_service(db, current_user.id, active_knowledge_base_id),
    )
    return service.search(q.strip(), result_types=_parse_types(types), tag=tag, favorite=favorite)
