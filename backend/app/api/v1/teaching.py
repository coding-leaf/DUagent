from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.course import Course, CourseEnrollment
from app.models.others import LearningPath, UserProfile, Evaluation
from app.models.quiz import QuizSession
from app.models.user import User

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])


async def _verify_teacher(class_id: str, current_user: User, db: AsyncSession) -> Course:
    result = await db.execute(select(Course).where(Course.id == class_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程不存在", "data": None},
        )
    if course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40300, "message": "无权访问此班级", "data": None},
        )
    return course


@router.get("/classes/{class_id}/students")
async def list_students(
    class_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)

    count_r = await db.execute(
        select(func.count(CourseEnrollment.id)).where(CourseEnrollment.course_id == class_id)
    )
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.course_id == class_id)
        .offset(offset)
        .limit(page_size)
    )
    enrollments = result.scalars().all()

    students = []
    for enr in enrollments:
        r = await db.execute(select(User).where(User.id == enr.student_id))
        u = r.scalar_one_or_none()
        if u:
            students.append({
                "id": u.id,
                "username": u.username,
                "real_name": u.real_name,
                "student_id": u.student_id,
                "major": u.major,
                "grade": u.grade,
                "joined_at": enr.joined_at.isoformat() if enr.joined_at else "",
            })

    return {
        "code": 200,
        "message": "success",
        "data": students,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/classes/{class_id}/students/{student_id}")
async def get_student_info(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)

    r = await db.execute(select(User).where(User.id == student_id))
    u = r.scalar_one_or_none()
    if u is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "学生不存在", "data": None},
        )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "real_name": u.real_name,
            "student_id": u.student_id,
            "role": u.role,
            "major": u.major,
            "grade": u.grade,
            "guidance_level": u.guidance_level,
            "courses": [],
            "created_at": u.created_at.isoformat() if u.created_at else "",
        },
    }


@router.get("/classes/{class_id}/students/{student_id}/learning")
async def get_student_learning(
    class_id: str,
    student_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)

    # Evaluation summary
    ev_result = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == student_id, Evaluation.course_id == class_id)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = ev_result.scalars().first()
    evaluation_summary = None
    if ev:
        evaluation_summary = {
            "overall_score": 75.0,
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else "",
        }

    # Profile summary
    pf_result = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == student_id, UserProfile.course_id == class_id)
    )
    pf = pf_result.scalar_one_or_none()
    profile_summary = None
    if pf:
        mastered = sum(1 for kc in pf.knowledge_coordinates if kc.get("status") == "mastered")
        weak = sum(1 for kc in pf.knowledge_coordinates if kc.get("status") != "mastered")
        profile_summary = {
            "knowledge_mastered": mastered,
            "knowledge_weak": weak,
            "modal_preference": list(pf.modal_preference.keys()) if pf.modal_preference else [],
        }

    # Path progress
    lp_result = await db.execute(
        select(LearningPath)
        .where(LearningPath.user_id == student_id, LearningPath.course_id == class_id)
    )
    lp = lp_result.scalar_one_or_none()
    path_progress = None
    if lp and lp.nodes:
        completed = sum(1 for n in lp.nodes if n.get("status") == "completed")
        path_progress = {
            "current_node": lp.current_node_name,
            "completed_nodes": completed,
            "total_nodes": len(lp.nodes),
        }

    # Quiz stats
    qs_result = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == student_id, QuizSession.course_id == class_id
        )
    )
    quiz_sessions = qs_result.scalars().all()
    quiz_stats = None
    if quiz_sessions:
        total_attempts = len(quiz_sessions)
        avg_score = sum(q.score for q in quiz_sessions) / total_attempts
        avg_time = sum(q.time_spent for q in quiz_sessions) / total_attempts
        quiz_stats = {
            "total_attempts": total_attempts,
            "avg_score": round(avg_score, 1),
            "avg_time_spent": int(avg_time),
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "evaluation_summary": evaluation_summary,
            "profile_summary": profile_summary,
            "path_progress": path_progress,
            "quiz_stats": quiz_stats,
        },
    }
