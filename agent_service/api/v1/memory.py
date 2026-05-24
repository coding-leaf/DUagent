from fastapi import APIRouter

from agent_service.agents.memory import compress_and_persist_memory
from agent_service.schemas.memory import MemoryCompressRequest, MemoryCompressResponse


router = APIRouter(prefix="/memory")


@router.post("/compress", response_model=MemoryCompressResponse, tags=["Memory"], summary="记忆压缩与事实提取")
async def compress_memory(request: MemoryCompressRequest) -> MemoryCompressResponse:
    return MemoryCompressResponse(code=200, message="success", data=await compress_and_persist_memory(request))
