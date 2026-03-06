from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.app_settings import load_app_settings_cache
from app.core.config import settings
from app.scheduler import scheduler, sync_conversations_job, sync_data_job
from app.utils import configure_logfire, logger

configure_logfire()


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Loading app settings from database")
    await load_app_settings_cache()

    if settings.SCHEDULER:
        logger.info("Starting scheduler")

        scheduler.add_job(  # type: ignore[call-arg]
            sync_conversations_job,
            trigger="interval",
            minutes=1,
            max_instances=1,
            id="sync_conversations",
            replace_existing=True,
        )

        scheduler.add_job(  # type: ignore[call-arg]
            sync_data_job,
            trigger="cron",
            hour=3,
            minute=0,
            # trigger="interval",
            # minutes=1,
            # TODO: change to europe / warsaw
            timezone="America/New_York",
            max_instances=1,
            id="sync_data",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("Scheduler started successfully")

    yield

    if settings.SCHEDULER:
        logger.info("Shutting down conversation sync scheduler")
        scheduler.shutdown()
        logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)


logfire.instrument_fastapi(app)

if settings.ALL_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALL_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(Exception)
async def exception_handler(request: Request, exception: Exception) -> JSONResponse:
    # TODO: don't expose exception details in production
    response = JSONResponse(
        {"error": str(exception)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    request_origin = request.headers.get("origin", "")
    if "*" in settings.ALL_CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif request_origin in settings.ALL_CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = request_origin

    return response


app.include_router(api_router, prefix=settings.API_STR)
