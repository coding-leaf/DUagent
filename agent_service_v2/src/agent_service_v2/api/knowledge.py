from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.tools.rag import (
    CatalogKnowledgeContextEmpty,
    build_catalog_kg_context,
    ingest_course_material,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/v2/knowledge")

_SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


class MaterialIngestionItem(BaseModel):
    storage_uri: str = Field(..., description="课本资源的相对路径或 URI")


class KnowledgeIngestionRequest(BaseModel):
    catalog_id: str = Field(..., description="课程资源目录（即 course_id）")
    materials: list[MaterialIngestionItem] = Field(..., description="待入库课本资源列表")


class KnowledgeIngestionMaterialResult(BaseModel):
    storage_uri: str
    status: str  # "ingested" | "failed"
    chunk_count: int = 0
    error: str | None = None


class KnowledgeIngestionResultData(BaseModel):
    catalog_id: str
    chunk_count: int
    materials: list[KnowledgeIngestionMaterialResult]


class KnowledgeIngestionAcceptedResponse(BaseModel):
    code: int = 202
    message: str = "accepted"
    data: KnowledgeIngestionResultData


@router.post(
    "/ingestions",
    response_model=KnowledgeIngestionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Knowledge"],
    summary="触发课程目录课本资料入库 (v2)",
)
async def create_knowledge_ingestion(
    request: KnowledgeIngestionRequest,
) -> KnowledgeIngestionAcceptedResponse | JSONResponse:
    """接收后端上传指令，对教材物理文件进行高精度 Parser、切片并写入 Qdrant。"""
    settings = AgentModelSettings()
    storage_root = Path(settings.COURSE_CATALOG_STORAGE_ROOT).resolve()
    
    material_results: list[KnowledgeIngestionMaterialResult] = []
    
    for material in request.materials:
        try:
            # 1. 安全解析和防范目录遍历
            source_path = _resolve_material_path(material.storage_uri, storage_root)
        except ValueError as exc:
            logger.warning("Relative path validation failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"code": 400, "message": str(exc), "data": None},
            )

        # 2. 检查物理文件是否存在与类型支持
        if not source_path.exists():
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="failed",
                    error="material does not exist",
                )
            )
            continue

        if source_path.is_file() and source_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="failed",
                    error=f"unsupported file type: {source_path.suffix}",
                )
            )
            continue

        # 3. 逐个高精度 Ingest，支持局部异常捕获
        try:
            chunk_count = await ingest_course_material(
                file_path=source_path,
                course_id=request.catalog_id,
                settings=settings,
            )
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="ingested",
                    chunk_count=chunk_count,
                )
            )
        except Exception as exc:
            logger.exception("Failed to ingest book %s: %s", material.storage_uri, exc)
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="failed",
                    error=str(exc),
                )
            )

    total_chunks = sum(item.chunk_count for item in material_results)
    return KnowledgeIngestionAcceptedResponse(
        code=202,
        message="accepted",
        data=KnowledgeIngestionResultData(
            catalog_id=request.catalog_id,
            chunk_count=total_chunks,
            materials=material_results,
        ),
    )


def _resolve_material_path(storage_uri: str, storage_root: Path) -> Path:
    """清理 URI 头部（如 local://）并安全校验，防御目录遍历遍历。"""
    stripped_uri = storage_uri.strip()
    if stripped_uri.startswith("local://"):
        stripped_uri = stripped_uri[len("local://") :]

    if not stripped_uri:
        raise ValueError("storage_uri must not be empty")

    path = PurePosixPath(stripped_uri)
    if path == PurePosixPath(".") or path.is_absolute() or ".." in path.parts:
        raise ValueError("storage_uri must be a safe relative path")

    parts = path.parts
    if parts and parts[0] == storage_root.name:
        parts = parts[1:]

    if not parts:
        raise ValueError("storage_uri must point to a material within course catalog storage root")

    resolved_path = storage_root.joinpath(*parts).resolve()
    try:
        # 严格校验必须处于 root 子树中
        resolved_path.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("storage_uri must stay within course catalog storage root") from exc

    if resolved_path == storage_root:
        raise ValueError("storage_uri must point to a material within course catalog storage root")

    return resolved_path


# =====================================================================
# V3 Multi-Agent Roadmap & Course Asset Generators (FastAPI Routes)
# =====================================================================

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

class KGGenerationRequest(BaseModel):
    context: str | None = Field(None, description="The course syllabus outline context")
    catalog_id: str | None = Field(None, description="Course catalog ID for catalog chunk input")
    source_type: str = Field("outline_text", description="Resource input origin")


class ResourceGenerationRequest(BaseModel):
    task_id: str = Field(..., description="Asynchronous task ID tracking this generation")
    course_id: str = Field(..., description="Associated host course entity")
    chapter: str | None = Field(None, description="Target syllabus chapter folder")
    knowledge_point: str | None = Field(None, description="Core pedagogical topic")
    resource_types: list[Literal["lesson", "diagram", "example"]] = Field(
        ...,
        min_length=1,
        description="Public resource types requested",
    )
    webhook_url: str = Field(..., description="Callback target to inject generated results")


class QuizGenerationRequest(BaseModel):
    task_id: str | None = Field(None, description="Task UUID")
    course_id: str = Field(..., description="Host entity")
    chapter: str | None = Field(None, description="Chapter")
    knowledge_point: str | None = Field(None, description="Pedagogical topic")
    question_types: list[str] = Field(default=["single_choice", "multi_choice", "code"])
    count: int = Field(default=3)
    user_id: str | None = Field(None, description="User ID for personalization")
    class_course_id: str | None = Field(None, description="Class Course ID")
    class_course_ids: list[str] | None = Field(None, description="Class Course IDs")
    difficulty: str | None = Field(None, description="Difficulty level")
    personalized: bool = Field(False, description="Whether this is a personalized request")
    personalization_context: dict[str, Any] | None = Field(None, description="Personalization context")
    source: str | None = Field(None, description="baseline or personalized")



from agent_service_v2.agents.leader_team import run_leader_team_kg_generation
from agent_service_v2.generators.public_resource_flow import run_public_resource_generation

@router.post(
    "/knowledge-graphs/generations",
    status_code=status.HTTP_200_OK,
    tags=["Knowledge Graph"],
    summary="一键由 Leader 规划提取课程知识图谱（V2）",
)
async def generate_v2_knowledge_graph(request: KGGenerationRequest):
    """一键通过 CoursePlannerAgent (Leader) 高度自检产生课程知识图谱大纲。"""
    settings = AgentModelSettings()
    try:
        if request.source_type == "catalog_chunks":
            if not request.catalog_id:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "code": 400,
                        "message": "catalog_id is required for catalog_chunks",
                        "data": None,
                    },
                )
            context = await build_catalog_kg_context(
                request.catalog_id,
                settings=settings,
            )
        else:
            context = (request.context or "").strip()
            if not context:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "code": 400,
                        "message": "context is required for outline_text",
                        "data": None,
                    },
                )

        data = await run_leader_team_kg_generation(settings, context)
        return {"code": 200, "message": "success", "data": data}
    except CatalogKnowledgeContextEmpty as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": 40918,
                "message": str(exc),
                "data": {"error_code": "kg_context_empty"},
            },
        )
    except Exception as exc:
        logger.exception("Leader team failed to extract KG: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"code": 502, "message": str(exc), "data": None},
        )


@router.post(
    "/resources/generations",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Resources"],
    summary="异步生成公共课程资源（V2）",
)
async def generate_v2_course_resources(request: ResourceGenerationRequest):
    """Generate typed public resources grounded in the course knowledge base."""
    settings = AgentModelSettings()

    asyncio.create_task(
        run_public_resource_generation(
            settings=settings,
            task_id=request.task_id,
            course_id=request.course_id,
            chapter=request.chapter,
            knowledge_point=request.knowledge_point,
            resource_types=list(request.resource_types),
            webhook_url=request.webhook_url
        )
    )
    return {"code": 202, "message": "accepted", "data": {"task_id": request.task_id, "status": "processing"}}


@router.post(
    "/quiz/generations",
    status_code=status.HTTP_200_OK,
    tags=["Assessment"],
    summary="快捷通过 Worker 智能体产生公共/个性化习题库（V2）",
)
async def generate_v2_quiz_questions(request: QuizGenerationRequest):
    """Allows instant direct call to Quiz Worker Agent to output custom choice and code challenges."""
    settings = AgentModelSettings()
    from agent_service_v2.agents.leader_team import ResourceWorkerAgent
    
    try:
        worker = ResourceWorkerAgent(settings)
        # Leverage existing quiz generator assets inside workers
        data = await worker.generate_asset(
            "quiz",
            request.chapter or "",
            request.knowledge_point or "",
            course_id=request.course_id,
            count=request.count,
            question_types=request.question_types,
            difficulty=request.difficulty,
            personalized=request.personalized,
            personalization_context=request.personalization_context,
        )
        return {"code": 200, "message": "success", "data": data}
    except Exception as exc:
        logger.exception("Quiz generation failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 500, "message": str(exc), "data": None},
        )
