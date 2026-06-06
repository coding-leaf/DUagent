from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.course import Course, CourseEnrollment
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])


async def _verify_teacher(class_id: str, current_user: User, db: AsyncSession) -> Course:
    result = await db.execute(
        select(Course).where(Course.id == class_id, Course.is_deleted == False)
    )
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
        select(func.count(CourseEnrollment.id)).where(
            CourseEnrollment.course_id == class_id, CourseEnrollment.is_deleted == False
        )
    )
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.course_id == class_id, CourseEnrollment.is_deleted == False)
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
                "joined_at": enr.create_time.isoformat() if enr.create_time else "",
            })

    return {
        "code": 200,
        "message": "success",
        "data": {"students": students, "total": total, "page": page, "page_size": page_size},
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
            "created_at": u.create_time.isoformat() if u.create_time else "",
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

    # Verify student is enrolled in this course
    enrollment_check = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.course_id == class_id,
            CourseEnrollment.is_deleted == False,
        )
    )
    if not enrollment_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "学生未入班", "data": None},
        )

    # Student info
    r = await db.execute(select(User).where(User.id == student_id))
    u = r.scalar_one_or_none()
    student_info = {}
    if u:
        student_info = {"id": u.id, "real_name": u.real_name, "student_id": u.student_id}

    # Evaluation
    ev_result = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == student_id, Evaluation.course_id == class_id, Evaluation.is_deleted == False)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = ev_result.scalars().first()
    evaluation_summary = None
    if ev:
        evaluation_summary = {
            "overall_score": 75.0,
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        }

    # Profile
    pf_result = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == student_id, UserProfile.course_id == class_id, UserProfile.is_deleted == False)
    )
    pf = pf_result.scalar_one_or_none()
    profile_summary = None
    if pf and pf.knowledge_coordinates:
        mastered = sum(1 for kc in pf.knowledge_coordinates if kc.get("status") == "mastered")
        weak = len(pf.knowledge_coordinates) - mastered
        profile_summary = {
            "knowledge_mastered": mastered,
            "knowledge_weak": weak,
            "modal_preference": list(pf.modal_preference.keys()) if pf.modal_preference else [],
        }

    # Path
    lp_result = await db.execute(
        select(LearningPath)
        .where(LearningPath.user_id == student_id, LearningPath.course_id == class_id, LearningPath.is_deleted == False)
    )
    lp = lp_result.scalar_one_or_none()
    path_progress = None
    if lp and lp.nodes:
        nds = lp.nodes if isinstance(lp.nodes, list) else []
        completed = sum(1 for n in nds if n.get("status") == "completed")
        path_progress = {
            "current_node": lp.current_node_name,
            "completed_nodes": completed,
            "total_nodes": len(nds),
        }

    # Quiz stats
    qs_result = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == student_id, QuizSession.course_id == class_id, QuizSession.is_deleted == False
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

    # weak_points: 按知识点聚合错题 top 5（条件聚合 + 过滤空知识点 + HAVING error_count > 0）
    error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
    total_attempts_expr = func.count(QuizAnswer.id)

    weak_points = []
    wp_result = await db.execute(
        select(
            QuizQuestion.knowledge_point,
            total_attempts_expr.label("total_attempts"),
            error_count_expr.label("error_count"),
        )
        .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
        .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
        .where(
            QuizSession.user_id == student_id,
            QuizSession.course_id == class_id,
            QuizSession.is_deleted == False,
            QuizAnswer.is_deleted == False,
            QuizQuestion.is_deleted == False,
            QuizQuestion.knowledge_point != "",
        )
        .group_by(QuizQuestion.knowledge_point)
        .having(error_count_expr > 0)
        .order_by(
            (error_count_expr / total_attempts_expr).desc(),
            error_count_expr.desc(),
        )
        .limit(5)
    )
    for row in wp_result:
        total = row.total_attempts
        errors = row.error_count or 0
        weak_points.append({
            "knowledge_point": row.knowledge_point,
            "error_count": errors,
            "total_attempts": total,
            "error_rate": round(errors / total, 2) if total > 0 else 0,
        })

    # recent_activity: 最近 5 次 QuizSession
    recent_activity = []
    ra_result = await db.execute(
        select(QuizSession)
        .where(
            QuizSession.user_id == student_id,
            QuizSession.course_id == class_id,
            QuizSession.is_deleted == False,
        )
        .order_by(QuizSession.create_time.desc())
        .limit(5)
    )
    for qs in ra_result.scalars().all():
        recent_activity.append({
            "quiz_id": qs.id,
            "chapter": qs.chapter or "",
            "score": qs.score,
            "correct_count": qs.correct_count,
            "total_count": qs.total_count,
            "time_spent": qs.time_spent,
            "created_at": qs.create_time.isoformat() if qs.create_time else "",
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "student": student_info,
            "evaluation_summary": evaluation_summary,
            "profile_summary": profile_summary,
            "path_progress": path_progress,
            "quiz_stats": quiz_stats,
            "weak_points": weak_points,
            "recent_activity": recent_activity,
        },
    }


@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)

    # 1. Get enrolled student IDs
    enrolled_result = await db.execute(
        select(CourseEnrollment.student_id).where(
            CourseEnrollment.course_id == class_id,
            CourseEnrollment.is_deleted == False,
        )
    )
    student_ids = [row[0] for row in enrolled_result.all()]

    if not student_ids:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "avg_quiz_score": None,
                "total_quiz_attempts": 0,
                "weak_points_top": [],
                "path_node_progress": {
                    "completed": 0,
                    "in_progress": 0,
                    "recommended": 0,
                    "pending": 0,
                    "total_nodes": 0,
                },
            },
        }

    # 2. avg_quiz_score & total_quiz_attempts
    quiz_result = await db.execute(
        select(
            func.avg(QuizSession.score).label("avg_score"),
            func.count(QuizSession.id).label("total_attempts"),
        ).where(
            QuizSession.course_id == class_id,
            QuizSession.user_id.in_(student_ids),
            QuizSession.is_deleted == False,
        )
    )
    quiz_row = quiz_result.one()
    avg_quiz_score = round(quiz_row.avg_score, 1) if quiz_row.avg_score is not None else None
    total_quiz_attempts = quiz_row.total_attempts or 0

    # 3. weak_points_top
    error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
    total_attempts_expr = func.count(QuizAnswer.id)

    wp_result = await db.execute(
        select(
            QuizQuestion.knowledge_point,
            total_attempts_expr.label("total_attempts"),
            error_count_expr.label("error_count"),
        )
        .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
        .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
        .where(
            QuizSession.course_id == class_id,
            QuizSession.user_id.in_(student_ids),
            QuizSession.is_deleted == False,
            QuizAnswer.is_deleted == False,
            QuizQuestion.is_deleted == False,
            QuizQuestion.knowledge_point != "",
        )
        .group_by(QuizQuestion.knowledge_point)
        .having(error_count_expr > 0)
        .order_by(
            (error_count_expr / total_attempts_expr).desc(),
            error_count_expr.desc(),
        )
        .limit(5)
    )

    weak_points_top = []
    for row in wp_result:
        total = row.total_attempts
        errors = row.error_count or 0
        weak_points_top.append({
            "knowledge_point": row.knowledge_point,
            "error_count": errors,
            "total_attempts": total,
            "error_rate": round(errors / total, 2) if total > 0 else 0,
        })

    # 4. path_node_progress
    lp_result = await db.execute(
        select(LearningPath).where(
            LearningPath.course_id == class_id,
            LearningPath.user_id.in_(student_ids),
            LearningPath.is_deleted == False,
        )
    )
    known_statuses = {"completed", "in_progress", "recommended", "pending"}
    progress = {s: 0 for s in known_statuses}
    for lp in lp_result.scalars().all():
        nodes = lp.nodes if isinstance(lp.nodes, list) else []
        for node in nodes:
            st = node.get("status")
            if st in known_statuses:
                progress[st] += 1

    return {
        "code": 200,
        "message": "success",
        "data": {
            "avg_quiz_score": avg_quiz_score,
            "total_quiz_attempts": total_quiz_attempts,
            "weak_points_top": weak_points_top,
            "path_node_progress": {
                **progress,
                "total_nodes": sum(progress.values()),
            },
        },
    }
