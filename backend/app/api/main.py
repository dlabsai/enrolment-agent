from fastapi import APIRouter

from app.api.routes import (
    analytics,
    auth,
    consent,
    conversations,
    evals,
    health,
    messages,
    models,
    prompts,
    settings,
    usage,
)

api_router = APIRouter()
api_router.include_router(settings.router)
api_router.include_router(auth.router)
api_router.include_router(messages.router)
api_router.include_router(models.router)
api_router.include_router(conversations.router)
api_router.include_router(usage.router)
api_router.include_router(evals.router)
api_router.include_router(analytics.router)
api_router.include_router(consent.router)
api_router.include_router(prompts.router)
api_router.include_router(health.router)
