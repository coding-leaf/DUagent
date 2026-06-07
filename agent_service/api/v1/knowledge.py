from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from agent_service.schemas.knowledge import (
    KnowledgeIngestionAcceptedResponse,
    KnowledgeIngestionMaterialResult,
    KnowledgeIngestionRequest,
    KnowledgeIngestionResultData,
)
from agent_service.tools.ingest_knowledge import ingest_course_knowledge


router = APIRouter(prefix="/knowledge")
_SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
_DEFAULT_STORAGE_ROOT = "storage/course_catalogs"


@router.post(
    "/ingestions",
    response_model=KnowledgeIngestionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Knowledge"],
    summary="触发课程目录知识入库",
)
async def create_knowledge_ingestion(
    request: KnowledgeIngestionRequest,
) -> KnowledgeIngestionAcceptedResponse | JSONResponse:
    """接收 Backend 课程目录资料路径，输入 catalog_id 和资料列表，输出逐资料入库结果。"""
    storage_root = _storage_root()
    material_results: list[KnowledgeIngestionMaterialResult] = []

    for material in request.materials:
        try:
            source_path = _resolve_material_path(material.storage_uri, storage_root)
        except ValueError as exc:
            return _bad_request_response(str(exc))
        if not source_path.exists():
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="failed",
                    message="material does not exist",
                )
            )
            continue
        if source_path.is_file() and source_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            material_results.append(
                KnowledgeIngestionMaterialResult(
                    storage_uri=material.storage_uri,
                    status="failed",
                    message=f"unsupported file type: {source_path.suffix}",
                )
            )
            continue
        result = await ingest_course_knowledge(source_path, course_id=request.catalog_id)
        material_results.append(
            KnowledgeIngestionMaterialResult(
                storage_uri=material.storage_uri,
                status="ingested",
                chunk_count=result.chunk_count,
            )
        )

    return KnowledgeIngestionAcceptedResponse(
        code=202,
        message="accepted",
        data=KnowledgeIngestionResultData(
            catalog_id=request.catalog_id,
            chunk_count=sum(item.chunk_count for item in material_results),
            materials=material_results,
        ),
    )


def _storage_root() -> Path:
    return Path(os.environ.get("COURSE_CATALOG_STORAGE_ROOT", _DEFAULT_STORAGE_ROOT)).resolve()


def _resolve_material_path(storage_uri: str, storage_root: Path) -> Path:
    relative_uri = _validate_relative_storage_uri(storage_uri)
    parts = relative_uri.parts
    if parts and parts[0] == storage_root.name:
        parts = parts[1:]
    resolved_path = storage_root.joinpath(*parts).resolve()
    try:
        resolved_path.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("storage_uri must stay within course catalog storage root") from exc
    return resolved_path


def _validate_relative_storage_uri(storage_uri: str) -> PurePosixPath:
    path = PurePosixPath(storage_uri)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("storage_uri must be a safe relative path")
    return path


def _bad_request_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"code": 400, "message": message, "data": None},
    )
