from fastapi import APIRouter

from service.api import chat, memories, review, search, sources

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(sources.router)
router.include_router(chat.router)
router.include_router(memories.router)
router.include_router(search.router)
router.include_router(review.router)
