from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from service.auth import get_current_user
from service.core.agent import AgentService
from service.db import get_db
from service.models import AgentProfile, RerankerProfile, User
from service.repositories.agent import AgentRepository
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository
from service.schemas import (
    AgentProfileCreate,
    AgentProfileRead,
    AgentProfileUpdate,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolLogRead,
    RerankerProfileCreate,
    RerankerProfileRead,
    RerankerProfileUpdate,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/profiles", response_model=list[AgentProfileRead])
def list_agent_profiles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    return [_agent_profile_read(profile, repo) for profile in repo.list_profiles()]


@router.post("/profiles", response_model=AgentProfileRead)
def create_agent_profile(data: AgentProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    return _agent_profile_read(repo.create_profile(data), repo)


@router.patch("/profiles/{profile_id}", response_model=AgentProfileRead)
def update_agent_profile(profile_id: int, data: AgentProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    try:
        return _agent_profile_read(repo.update_profile(profile_id, data), repo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/activate", response_model=AgentProfileRead)
def activate_agent_profile(profile_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    try:
        return _agent_profile_read(repo.activate_profile(profile_id), repo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/runs", response_model=AgentRunResponse)
def run_agent(data: AgentRunRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = AgentService(
        AgentRepository(db, user_id=current_user.id),
        SourceRepository(db, user_id=current_user.id),
        ChunkRepository(db, user_id=current_user.id),
        MemoryRepository(db, user_id=current_user.id),
        ConversationRepository(db, user_id=current_user.id),
        OrganizationRepository(db, user_id=current_user.id),
    )
    return service.run(data.message)


@router.get("/tool-logs", response_model=list[AgentToolLogRead])
def list_tool_logs(limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    bounded_limit = min(max(limit, 1), 100)
    return AgentRepository(db, user_id=current_user.id).list_tool_logs(limit=bounded_limit)


@router.get("/reranker-profiles", response_model=list[RerankerProfileRead])
def list_reranker_profiles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [_reranker_profile_read(profile) for profile in AgentRepository(db, user_id=current_user.id).list_reranker_profiles()]


@router.post("/reranker-profiles", response_model=RerankerProfileRead)
def create_reranker_profile(data: RerankerProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _reranker_profile_read(AgentRepository(db, user_id=current_user.id).create_reranker_profile(data))


@router.patch("/reranker-profiles/{profile_id}", response_model=RerankerProfileRead)
def update_reranker_profile(profile_id: int, data: RerankerProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    try:
        return _reranker_profile_read(repo.update_reranker_profile(profile_id, data))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/reranker-profiles/{profile_id}/activate", response_model=RerankerProfileRead)
def activate_reranker_profile(profile_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = AgentRepository(db, user_id=current_user.id)
    try:
        return _reranker_profile_read(repo.activate_reranker_profile(profile_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _agent_profile_read(profile: AgentProfile, repo: AgentRepository) -> AgentProfileRead:
    return AgentProfileRead(
        id=profile.id,
        name=profile.name,
        instructions=profile.instructions,
        enabled_tools=repo.enabled_tools(profile),
        require_approval=profile.require_approval,
        is_active=profile.is_active,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _reranker_profile_read(profile: RerankerProfile) -> RerankerProfileRead:
    return RerankerProfileRead(
        id=profile.id,
        name=profile.name,
        provider=profile.provider,
        base_url=profile.base_url,
        model=profile.model,
        api_key_configured=bool(profile.api_key),
        top_n=profile.top_n,
        is_active=profile.is_active,
        status=profile.status,
        last_error=profile.last_error,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
