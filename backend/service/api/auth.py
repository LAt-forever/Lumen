from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from service.auth import authenticate_user, create_access_token, create_user, ensure_bootstrap_user, get_current_user
from service.config import Settings, get_settings
from service.db import get_db
from service.models import User
from service.schemas import AuthTokenRead, LoginRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User, settings: Settings) -> AuthTokenRead:
    return AuthTokenRead(access_token=create_access_token(user, settings), user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthTokenRead)
def login(data: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    ensure_bootstrap_user(db, settings)
    user = authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_response(user, settings)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout():
    return {"status": "ok"}


@router.post("/register", response_model=AuthTokenRead, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not settings.registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
    try:
        user = create_user(db, data.email, data.password, require_new=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from exc
    return _token_response(user, settings)
