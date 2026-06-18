from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask


def catalog_item(catalog: CourseCatalog) -> dict:
    return {
        "id": catalog.id,
        "title": catalog.title,
        "description": catalog.description or "",
        "status": catalog.status,
        "knowledge_status": catalog.knowledge_status,
        "material_count": catalog.material_count,
        "last_ingestion_task_id": catalog.last_ingestion_task_id,
        "last_ingestion_status": catalog.last_ingestion_status,
        "chunk_count": catalog.chunk_count or 0,
        "last_error": catalog.last_error,
        "created_at": catalog.create_time.isoformat() if catalog.create_time else "",
    }


def material_item(material: CourseCatalogMaterial, include_storage_uri: bool = False) -> dict:
    item = {
        "id": material.id,
        "catalog_id": material.catalog_id,
        "filename": material.filename,
        "source_type": material.source_type,
        "file_size": material.file_size or 0,
        "status": material.status,
        "chunk_count": material.chunk_count or 0,
        "last_error": material.last_error,
        "ingested_at": material.ingested_at.isoformat() if material.ingested_at else None,
        "created_at": material.create_time.isoformat() if material.create_time else "",
    }
    if include_storage_uri:
        item["storage_uri"] = material.storage_uri
    return item


def knowledge_graph_summary(graph) -> dict:
    return {
        "graph_id": graph.id,
        "course_id": graph.course_id,
        "version": graph.version,
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "is_active": graph.is_active,
        "created_at": graph.create_time.isoformat() if graph.create_time else "",
    }


def knowledge_graph_task_summary(task: AsyncTask) -> dict:
    return {
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.create_time.isoformat() if task.create_time else "",
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
