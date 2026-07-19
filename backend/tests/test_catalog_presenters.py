from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.catalog_presenters import (
    catalog_item,
    knowledge_graph_summary,
    knowledge_graph_task_summary,
    material_item,
)


def test_catalog_item_response_shape():
    created_at = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    catalog = SimpleNamespace(
        id="cat1",
        title="数据结构",
        description=None,
        status="ready",
        knowledge_status="partial",
        material_count=2,
        last_ingestion_task_id="task1",
        last_ingestion_status="completed",
        chunk_count=None,
        last_error=None,
        create_time=created_at,
    )

    assert catalog_item(catalog) == {
        "id": "cat1",
        "title": "数据结构",
        "description": "",
        "status": "ready",
        "knowledge_status": "partial",
        "material_count": 2,
        "last_ingestion_task_id": "task1",
        "last_ingestion_status": "completed",
        "chunk_count": 0,
        "last_error": None,
        "created_at": created_at.isoformat(),
    }


def test_material_item_response_shape_and_storage_uri_flag():
    created_at = datetime(2026, 6, 18, 8, 1, tzinfo=timezone.utc)
    ingested_at = datetime(2026, 6, 18, 8, 2, tzinfo=timezone.utc)
    material = SimpleNamespace(
        id="mat1",
        catalog_id="cat1",
        filename="intro.pdf",
        source_type="file",
        file_size=None,
        status="ingested",
        chunk_count=None,
        last_error=None,
        ingested_at=ingested_at,
        create_time=created_at,
        storage_uri="course_catalogs/cat1/mat1/intro.pdf",
    )

    hidden = material_item(material)
    visible = material_item(material, include_storage_uri=True)

    assert "storage_uri" not in hidden
    assert visible["storage_uri"] == "course_catalogs/cat1/mat1/intro.pdf"
    assert visible["file_size"] == 0
    assert visible["chunk_count"] == 0
    assert visible["ingested_at"] == ingested_at.isoformat()


def test_knowledge_graph_presenter_response_shapes():
    created_at = datetime(2026, 6, 18, 8, 3, tzinfo=timezone.utc)
    completed_at = datetime(2026, 6, 18, 8, 4, tzinfo=timezone.utc)
    graph = SimpleNamespace(
        id="graph1",
        course_id="course1",
        version=3,
        source_type="route_a",
        generation_strategy="route_a_prune",
        nodes=[{"id": "n1"}],
        edges=[{"source": "n1", "target": "n2"}],
        is_active=True,
        create_time=created_at,
    )
    task = SimpleNamespace(
        id="task1",
        status="completed",
        progress=100,
        error_code=None,
        error_message="",
        create_time=created_at,
        completed_at=completed_at,
    )

    assert knowledge_graph_summary(graph) == {
        "graph_id": "graph1",
        "course_id": "course1",
        "version": 3,
        "source_type": "route_a",
        "generation_strategy": "route_a_prune",
        "node_count": 1,
        "edge_count": 1,
        "is_active": True,
        "created_at": created_at.isoformat(),
    }
    assert knowledge_graph_task_summary(task)["completed_at"] == completed_at.isoformat()
