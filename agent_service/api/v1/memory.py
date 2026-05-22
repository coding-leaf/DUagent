from fastapi import APIRouter

from agent_service.schemas.memory import MemoryCompressRequest, MemoryCompressResponse, MemoryCompressResult


router = APIRouter(prefix="/memory")


@router.post("/compress", response_model=MemoryCompressResponse, tags=["Memory"], summary="记忆压缩与事实提取")
async def compress_memory(_: MemoryCompressRequest) -> MemoryCompressResponse:
    return MemoryCompressResponse(code=200, message="success", data=MemoryCompressResult())
