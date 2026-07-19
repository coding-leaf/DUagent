from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.code_problem import CodeProblemSubmissionRequest
from app.services.code_problem_service import CodeProblemValidationError
from app.services.code_problem_submission_service import (
    get_personal_code_problem_detail,
    start_code_problem_submission,
)

router = APIRouter(prefix="/api/v1/code-problems", tags=["code-problems"])


@router.get("/{problem_id}")
async def get_private_code_problem(
    problem_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem = await get_personal_code_problem_detail(
        db,
        problem_id=problem_id,
        owner_user_id=current_user.id,
    )
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "代码题不存在", "data": None},
        )
    return {"code": 200, "message": "success", "data": problem}


@router.post("/{problem_id}/submissions")
async def submit_private_code_problem(
    problem_id: str,
    req: CodeProblemSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        task_id = await start_code_problem_submission(
            db,
            problem_id=problem_id,
            owner_user_id=current_user.id,
            code=req.code,
        )
    except CodeProblemValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "提交代码不合法", "data": None},
        )
    if task_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "代码题不存在", "data": None},
        )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"code": 202, "message": "accepted", "data": {"task_id": task_id}},
    )
