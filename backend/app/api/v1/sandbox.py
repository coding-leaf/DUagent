from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.oj_execution_service import execute_code_in_oj, OJExecutionError

router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])


class SandboxExecuteRequest(BaseModel):
    code: str = Field(..., description="要运行的源代码")
    language: str = Field(..., description="编程语言标识 (如 c, cpp, python)")
    stdin: str = Field("", description="标准输入数据")


@router.post("/execute")
async def execute_sandbox_code(
    req: SandboxExecuteRequest,
    _current_user: User = Depends(get_current_user),
):
    """
    学生画布卡片调用的代码运行接口。
    若 OJ 服务不可用，返回 200 及降级信息提示前端显示。
    """
    try:
        result = await execute_code_in_oj(
            code=req.code,
            language=req.language,
            stdin=req.stdin,
        )
        return {"code": 200, "message": "success", "data": result}
    except OJExecutionError as exc:
        if exc.reason == "unsupported_language":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 40001, "message": exc.message, "data": None},
            )
        # Sandbox execution degradation fallback
        return {
            "code": 200,
            "message": "degraded",
            "data": {
                "status": "degraded",
                "reason": exc.reason,
                "compile_status": "UNKNOWN",
                "execution": None,
                "message": "评测服务暂时不可用，请稍后再试",
            }
        }
