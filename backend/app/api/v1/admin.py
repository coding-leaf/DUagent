from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.security import hash_password
from app.models.others import AgentLog, OperationLog
from app.models.user import User
from app.schemas.admin import AdminUpdateUserRequest

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str = Query(None),
    keyword: str = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(User.is_deleted == False)
    if role:
        query = query.where(User.role == role)
    if keyword:
        query = query.where(
            (User.email.contains(keyword)) | (User.username.contains(keyword))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    users = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "real_name": u.real_name,
                    "role": u.role,
                    "major": u.major,
                    "grade": u.grade,
                    "created_at": u.create_time.isoformat() if u.create_time else "",
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    req: AdminUpdateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "用户不存在", "data": None},
        )

    if req.username is not None:
        target.username = req.username
    if req.real_name is not None:
        target.real_name = req.real_name
    if req.student_id is not None:
        target.student_id = req.student_id
    if req.role is not None:
        target.role = req.role
    if req.major is not None:
        target.major = req.major
    if req.grade is not None:
        target.grade = req.grade
    if req.new_password is not None:
        target.password_hash = hash_password(req.new_password)
    await db.flush()
    await db.refresh(target)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": target.id,
            "username": target.username,
            "email": target.email,
            "real_name": target.real_name,
            "role": target.role,
            "major": target.major,
            "grade": target.grade,
            "created_at": target.create_time.isoformat() if target.create_time else "",
        },
    }


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40302, "message": "不可移除自己", "data": None},
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "用户不存在", "data": None},
        )

    target.is_active = False
    await db.flush()
    return {"code": 200, "message": "success", "data": {}}


@router.get("/logs/agent")
async def agent_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgentLog).where(AgentLog.is_deleted == False)
    if start_date:
        query = query.where(AgentLog.timestamp >= start_date)
    if end_date:
        query = query.where(AgentLog.timestamp <= end_date)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(AgentLog.timestamp.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "timestamp": l.timestamp.isoformat() if l.timestamp else "",
                    "agent_type": l.agent_type,
                    "endpoint": l.endpoint,
                    "latency_ms": l.latency_ms,
                    "tokens_used": l.tokens_used,
                    "status": l.status,
                    "error_message": l.error_message,
                    "security_blocked": l.security_blocked,
                }
                for l in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/logs/operations")
async def operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(OperationLog).where(OperationLog.is_deleted == False)
    if event_type:
        query = query.where(OperationLog.event_type == event_type)
    if start_date:
        query = query.where(OperationLog.timestamp >= start_date)
    if end_date:
        query = query.where(OperationLog.timestamp <= end_date)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(OperationLog.timestamp.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "timestamp": l.timestamp.isoformat() if l.timestamp else "",
                    "event_type": l.event_type,
                    "user_id": l.user_id,
                    "description": l.description,
                    "ip_address": l.ip_address,
                    "detail": l.detail,
                }
                for l in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
