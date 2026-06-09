from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from service.core.global_search import GlobalSearchService
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import GlobalSearchResultRead

router = APIRouter(prefix="/api/global-search", tags=["global-search"])

_ALLOWED_TYPES = {"source_chunk", "source", "memory", "message"}


def _parse_types(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    parsed: set[str] = set()
    for value in values:
        parsed.update(part.strip() for part in value.split(",") if part.strip())
    return {value for value in parsed if value in _ALLOWED_TYPES} or None


@router.get("", response_model=list[GlobalSearchResultRead])
def global_search(
    q: str = Query(min_length=1),
    types: list[str] | None = Query(default=None),
    tag: str | None = None,
    favorite: bool = False,
    db: Session = Depends(get_db),
):
    service = GlobalSearchService(
        SourceRepository(db),
        ChunkRepository(db),
        MemoryRepository(db),
        ConversationRepository(db),
        OrganizationRepository(db),
    )
    return service.search(q.strip(), result_types=_parse_types(types), tag=tag, favorite=favorite)
