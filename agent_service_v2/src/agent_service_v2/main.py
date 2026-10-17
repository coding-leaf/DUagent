from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_service_v2.api.workbench import router as workbench_router
from agent_service_v2.api.knowledge import router as knowledge_router
from agent_service_v2.api.evaluation import router as evaluation_router
from agent_service_v2.api.personalized_resources import (
    router as personalized_resources_router,
    shutdown_generation_sessions,
)
from agent_service_v2.tools.web_search_mcp import build_web_search_runtime_from_environ


@asynccontextmanager
async def lifespan(app: FastAPI):
    web_search_runtime = build_web_search_runtime_from_environ()
    app.state.web_search_runtime = web_search_runtime
    app.state.web_search_client = None
    try:
        app.state.web_search_client = await web_search_runtime.start()
        yield
    finally:
        app.state.web_search_client = None
        shutdown_generation_sessions()
        await web_search_runtime.close()


app = FastAPI(title="EDUagent Agent Service v2", lifespan=lifespan)
app.include_router(workbench_router)
app.include_router(knowledge_router)
app.include_router(evaluation_router)
app.include_router(personalized_resources_router)
