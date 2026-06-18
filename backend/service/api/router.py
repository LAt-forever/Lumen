from fastapi import APIRouter

from service.api import agent, chat, global_search, ingestion_jobs, memories, organization, review, search, settings, sources, status

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(sources.router)
router.include_router(ingestion_jobs.router)
router.include_router(chat.router)
router.include_router(memories.router)
router.include_router(search.router)
router.include_router(global_search.router)
router.include_router(review.router)
router.include_router(settings.router)
router.include_router(organization.router)
router.include_router(status.router)
router.include_router(agent.router)
