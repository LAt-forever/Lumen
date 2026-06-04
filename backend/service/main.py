from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service.api.router import router
from service.db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Lumen API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    return app


app = create_app()
