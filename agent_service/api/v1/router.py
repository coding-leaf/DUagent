from fastapi import APIRouter

from agent_service.api.v1 import health

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
# Add other routers here as they are developed
# api_router.include_router(tutoring.router, prefix="/tutoring", tags=["tutoring"])
# api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
# api_router.include_router(assessment.router, prefix="/assessment", tags=["assessment"])
# api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
# api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
