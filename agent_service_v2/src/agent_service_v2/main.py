from fastapi import FastAPI

from agent_service_v2.api.workbench import router as workbench_router
from agent_service_v2.api.knowledge import router as knowledge_router
from agent_service_v2.api.evaluation import router as evaluation_router

app = FastAPI(title="EDUagent Agent Service v2")
app.include_router(workbench_router)
app.include_router(knowledge_router)
app.include_router(evaluation_router)

