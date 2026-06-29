from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.tagging import TagSuggestionService
from service.db import get_db
from service.models import User
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    FavoriteCreate,
    FavoriteRead,
    TagAssignmentCreate,
    TagAssignmentRead,
    TagCreate,
    TagRead,
    TagSuggestionRead,
)

router = APIRouter(tags=["organization"])


def _ensure_target_exists(db: Session, target_type: str, target_id: int, user_id: int) -> None:
    if target_type == "source" and SourceRepository(db, user_id=user_id).exists(target_id):
        return
    if target_type == "memory" and MemoryRepository(db, user_id=user_id).exists_active(target_id):
        return
    if target_type == "message" and ConversationRepository(db, user_id=user_id).get_message(target_id) is not None:
        return
    raise HTTPException(status_code=404, detail=f"{target_type} target not found")


@router.get("/api/tags", response_model=list[TagRead])
def list_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return OrganizationRepository(db, user_id=current_user.id).list_tags()


@router.post("/api/tags", response_model=TagRead)
def create_tag(data: TagCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return OrganizationRepository(db, user_id=current_user.id).create_tag(data.name, data.color)


@router.post("/api/tags/assignments", response_model=TagAssignmentRead)
def assign_tag(data: TagAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = OrganizationRepository(db, user_id=current_user.id)
    if repo.get_tag(data.tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    _ensure_target_exists(db, data.target_type, data.target_id, current_user.id)
    return repo.assign_tag(data.tag_id, data.target_type, data.target_id)


@router.delete("/api/tags/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    OrganizationRepository(db, user_id=current_user.id).delete_assignment(assignment_id)
    return Response(status_code=204)


@router.get("/api/tag-suggestions", response_model=list[TagSuggestionRead])
def list_tag_suggestions(
    target_type: str | None = None,
    target_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = OrganizationRepository(db, user_id=current_user.id)
    TagSuggestionService(
        SourceRepository(db, user_id=current_user.id),
        MemoryRepository(db, user_id=current_user.id),
        ConversationRepository(db, user_id=current_user.id),
        repo,
    ).ensure_suggestions_for_existing()
    return repo.pending_suggestions(target_type=target_type, target_id=target_id)


@router.post("/api/tag-suggestions/{suggestion_id}/confirm", response_model=TagAssignmentRead)
def confirm_tag_suggestion(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return OrganizationRepository(db, user_id=current_user.id).confirm_suggestion(suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/tag-suggestions/{suggestion_id}/ignore", response_model=TagSuggestionRead)
def ignore_tag_suggestion(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return OrganizationRepository(db, user_id=current_user.id).ignore_suggestion(suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/favorites", response_model=list[FavoriteRead])
def list_favorites(target_type: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return OrganizationRepository(db, user_id=current_user.id).list_favorites(target_type=target_type)


@router.post("/api/favorites", response_model=FavoriteRead)
def favorite(data: FavoriteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_target_exists(db, data.target_type, data.target_id, current_user.id)
    return OrganizationRepository(db, user_id=current_user.id).favorite(data.target_type, data.target_id)


@router.delete("/api/favorites/{target_type}/{target_id}", status_code=204)
def unfavorite(target_type: str, target_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_target_exists(db, target_type, target_id, current_user.id)
    OrganizationRepository(db, user_id=current_user.id).unfavorite(target_type, target_id)
    return Response(status_code=204)
