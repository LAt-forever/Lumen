from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service.api.router import router
from service.auth import ensure_bootstrap_user
from service.core.security import configure_log_redaction
from service import db as dbmod


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_log_redaction()
    dbmod.init_db()
    with dbmod.SessionLocal() as db:
        ensure_bootstrap_user(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Lumen API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    return app


app = create_app()
