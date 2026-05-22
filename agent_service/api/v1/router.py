from fastapi import APIRouter

from agent_service.api.v1 import assessment, evaluation, health, learning_path, memory, profile, resources, tutoring

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(tutoring.router)
api_router.include_router(profile.router)
api_router.include_router(evaluation.router)
api_router.include_router(assessment.router)
api_router.include_router(learning_path.router)
api_router.include_router(resources.router)
api_router.include_router(memory.router)
