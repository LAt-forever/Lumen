from collections.abc import Generator
from importlib import import_module

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from service.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine: Engine
SessionLocal: sessionmaker[Session]


def configure_database(database_url: str | None = None) -> None:
    global engine, SessionLocal

    url = database_url or get_settings().database_url
    engine = create_engine(url, connect_args=_connect_args(url))
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


configure_database()


def init_db() -> None:
    try:
        import_module("service.models")
    except ModuleNotFoundError as exc:
        if exc.name != "service.models":
            raise

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
