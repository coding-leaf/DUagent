from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.personalized_resource_generation import (
    PersonalizedDraftCreateRequest,
    PersonalizedGenerationScopeRequest,
    PersonalizedReviewRequest,
    PersonalizedValidationRequest,
)
from app.services.code_problem_service import publish_reviewed_personal_problem
from app.services.personalized_resource_generation_service import (
    PersonalizedResourceGenerationService,
    ResourcePublicationError,
)

router = APIRouter(
    prefix="/internal/personalized-resources",
    tags=["internal-personalized-resources"],
)


def verify_internal_agent_token(
    token: str | None = Header(default=None, alias="X-Internal-Agent-Token"),
) -> None:
    if not settings.INTERNAL_AGENT_TOKEN or token != settings.INTERNAL_AGENT_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.post("/drafts")
async def create_draft(
    req: PersonalizedDraftCreateRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    generation = await PersonalizedResourceGenerationService(db).create_draft(
        **req.model_dump()
    )
    return _success({"generation_id": generation.id, "status": generation.status})


@router.post("/{generation_id}/validation")
async def attach_validation(
    generation_id: str,
    req: PersonalizedValidationRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    generation = await PersonalizedResourceGenerationService(db).record_validation(
        generation_id,
        req.report,
        user_id=req.user_id,
        course_id=req.course_id,
    )
    return _success({"generation_id": generation.id, "status": generation.status})


@router.post("/{generation_id}/review")
async def attach_review(
    generation_id: str,
    req: PersonalizedReviewRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    report = req.model_dump(exclude={"user_id", "course_id", "resource_kind"})
    generation = await PersonalizedResourceGenerationService(db).record_review(
        generation_id,
        report,
        user_id=req.user_id,
        course_id=req.course_id,
    )
    return _success({"generation_id": generation.id, "status": generation.status})


@router.post("/{generation_id}/publish")
async def publish_generation(
    generation_id: str,
    req: PersonalizedGenerationScopeRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        if req.resource_kind == "code_problem":
            created = await publish_reviewed_personal_problem(
                db, generation_id=generation_id, user_id=req.user_id, course_id=req.course_id
            )
            data = {"code_problem_id": created.problem.id, "status": "published"}
        else:
            resource = await PersonalizedResourceGenerationService(db).publish(
                generation_id, user_id=req.user_id, course_id=req.course_id
            )
            data = {"resource_id": resource.id, "resource_type": resource.type, "status": "published"}
    except (ResourcePublicationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _success(data)


def _success(data: dict) -> dict:
    return {"code": 200, "message": "success", "data": data}
