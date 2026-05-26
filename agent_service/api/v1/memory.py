from fastapi import APIRouter

from agent_service.agents.memory import compress_and_persist_memory, compress_memory_with_llm
from agent_service.core.ai import get_ai_providers
from agent_service.schemas.memory import MemoryCompressRequest, MemoryCompressResponse


router = APIRouter(prefix="/memory")


@router.post("/compress", response_model=MemoryCompressResponse, tags=["Memory"], summary="记忆压缩与事实提取")
async def compress_memory(request: MemoryCompressRequest) -> MemoryCompressResponse:
    providers = get_ai_providers()
    compress_result = await compress_memory_with_llm(request, getattr(providers, "chat", None))
    return MemoryCompressResponse(
        code=200, message="success",
        data=await compress_and_persist_memory(request, compress_result=compress_result),
    )
