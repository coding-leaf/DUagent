from fastapi import FastAPI

from agent_service_v2.api.workbench import router as workbench_router
from agent_service_v2.api.knowledge import router as knowledge_router
from agent_service_v2.api.evaluation import router as evaluation_router
from agent_service_v2.api.personalized_resources import router as personalized_resources_router
from agent_service_v2.team_app import team_runtime_app

app = FastAPI(title="EDUagent Agent Service v2")
app.include_router(workbench_router)
app.include_router(knowledge_router)
app.include_router(evaluation_router)
app.include_router(personalized_resources_router)
app.mount("/agent/v2/team-runtime", team_runtime_app)
