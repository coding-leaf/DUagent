from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_service.api.v1.router import api_router
from agent_service.core.config import settings
from agent_service.core.qdrant import init_collections, get_qdrant_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize resources
    init_collections()
    yield
    # Shutdown: Clean up resources (if needed)
    # client = get_qdrant_client()
    # client.close() # Qdrant local client doesn't strictly require explicit close, but good practice if available

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_service.main:app", host="0.0.0.0", port=8002, reload=True)
