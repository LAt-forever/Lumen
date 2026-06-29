from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.config import Settings, get_settings
from service.core.status import StatusService
from service.db import get_db
from service.models import User
from service.repositories.conversations import ConversationRepository
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.provider_profiles import ProviderProfileRepository
from service.repositories.sources import SourceRepository
from service.schemas import StatusSummaryRead

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("", response_model=StatusSummaryRead)
def status_summary(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return StatusService(
        settings,
        SourceRepository(db, user_id=current_user.id),
        IngestionJobRepository(db, user_id=current_user.id),
        MemoryRepository(db, user_id=current_user.id),
        ConversationRepository(db, user_id=current_user.id),
        OrganizationRepository(db, user_id=current_user.id),
        ProviderProfileRepository(db, user_id=current_user.id),
    ).summary()
