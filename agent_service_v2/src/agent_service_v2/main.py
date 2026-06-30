from fastapi import FastAPI

from agent_service_v2.api.workbench import router as workbench_router

app = FastAPI(title="EDUagent Agent Service v2")
app.include_router(workbench_router)
