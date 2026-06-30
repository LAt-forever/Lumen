from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.db import get_db
from service.models import User
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.schemas import KnowledgeBaseCreate, KnowledgeBaseRead, KnowledgeBaseUpdate

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


def _repository(db: Session, current_user: User) -> KnowledgeBaseRepository:
    return KnowledgeBaseRepository(db, user_id=current_user.id)


def _raise_http(exc: ValueError) -> None:
    message = str(exc)
    code = status.HTTP_404_NOT_FOUND if "not found" in message else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _repository(db, current_user).list()


@router.post("", response_model=KnowledgeBaseRead)
def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _repository(db, current_user).create(data)
    except ValueError as exc:
        _raise_http(exc)


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    knowledge_base_id: int,
    data: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _repository(db, current_user).update(knowledge_base_id, data)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/{knowledge_base_id}/archive", response_model=KnowledgeBaseRead)
def archive_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _repository(db, current_user).archive(knowledge_base_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/{knowledge_base_id}/restore", response_model=KnowledgeBaseRead)
def restore_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _repository(db, current_user).restore(knowledge_base_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/{knowledge_base_id}/activate", response_model=KnowledgeBaseRead)
def activate_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _repository(db, current_user).require_active(knowledge_base_id)
    except ValueError as exc:
        _raise_http(exc)


@router.delete("/{knowledge_base_id}", status_code=204)
def delete_knowledge_base(
    knowledge_base_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _repository(db, current_user).delete_empty(knowledge_base_id)
    except ValueError as exc:
        _raise_http(exc)
    return Response(status_code=204)
