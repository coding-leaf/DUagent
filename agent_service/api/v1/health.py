from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the Agent Service.
    """
    return {
        "code": 200,
        "message": "success",
        "data": {
            "status": "healthy",
            "qdrant_connected": False, # TODO: Implement actual check
            "model_loaded": False,     # TODO: Implement actual check
            "model_name": "none",
            "uptime_seconds": 0        # TODO: Implement actual check
        }
    }
