from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User
from app.services.teaching_service import TeachingService

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])


@router.get("/classes/{class_id}/students")
async def list_students(
    class_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).list_students(
        class_id,
        current_user,
        page,
        page_size,
    )
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/students/{student_id}")
async def get_student_info(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_student_info(
        class_id,
        student_id,
        current_user,
    )
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/students/{student_id}/learning")
async def get_student_learning(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_student_learning(
        class_id,
        student_id,
        current_user,
    )
    return {"code": 200, "message": "success", "data": data}


@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_class_insights(class_id, current_user)
    return {"code": 200, "message": "success", "data": data}
