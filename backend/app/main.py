from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    admin, auth, catalogs, courses, evaluation, internal_ai_chat, learning_path,
    code_problems, learning_activities, personalized_resources, profile, quiz, resources,
    sandbox, tasks, teaching, tutoring, users, webhooks,
)
from app.core.config import settings
from app.db.session import init_db
from app.exceptions.base import DomainException
from app.exceptions.handlers import domain_exception_handler


async def _recover_orphaned_background_tasks() -> None:
    """启动时将残留的进程内后台 processing 任务标记为 failed。

    只覆盖使用 asyncio.create_task 且没有外部恢复机制的任务：
    profile_refresh / evaluation_refresh / learning_path_refresh / kg_generation。
    进程重启后这些协程会丢失。
    resource_generation / quiz_generation 不在此范围。
    """
    import logging
    from datetime import datetime, timezone

    from sqlalchemy import update as sql_update
    from app.db.session import async_session_factory
    from app.models.others import AsyncTask

    logger = logging.getLogger(__name__)
    _recoverable_task_types = [
        "profile_refresh",
        "evaluation_refresh",
        "learning_path_refresh",
        "kg_generation",
        "code_problem_judging",
    ]

    async with async_session_factory() as db:
        result = await db.execute(
            sql_update(AsyncTask)
            .where(
                AsyncTask.status == "processing",
                AsyncTask.task_type.in_(_recoverable_task_types),
            )
            .values(
                status="failed",
                error_code=None,
                error_message="服务重启，后台任务丢失",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        if result.rowcount:
            logger.warning(
                "Startup recovery: marked %d orphaned background tasks as failed",
                result.rowcount,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _recover_orphaned_background_tasks()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_exception_handler(DomainException, domain_exception_handler)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from fastapi.exceptions import HTTPException as FastAPIHTTPException
    if isinstance(exc, FastAPIHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": 50000, "message": str(exc.detail), "data": None},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 50000, "message": "服务端内部错误", "data": None},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(catalogs.router)
app.include_router(internal_ai_chat.router)
app.include_router(sandbox.router)
app.include_router(code_problems.router)
app.include_router(courses.router)
app.include_router(teaching.router)
app.include_router(admin.router)
app.include_router(evaluation.router)
app.include_router(learning_activities.router)
app.include_router(profile.router)
app.include_router(learning_path.router)
app.include_router(quiz.router)
app.include_router(resources.router)
app.include_router(personalized_resources.router)
app.include_router(tutoring.router)
app.include_router(tasks.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
