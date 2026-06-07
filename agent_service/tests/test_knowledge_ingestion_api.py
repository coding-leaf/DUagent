from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_service.api.v1.router import api_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/agent/v1")
    return TestClient(app)


def test_knowledge_ingestion_rejects_parent_storage_uri(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "../secret.md"}],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert "storage_uri" in payload["message"]


def test_knowledge_ingestion_rejects_absolute_storage_uri(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "/tmp/secret.md"}],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert "storage_uri" in payload["message"]


def test_knowledge_ingestion_rejects_empty_storage_uri(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": ""}],
        },
    )

    assert response.status_code == 422


def test_knowledge_ingestion_rejects_empty_catalog_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "",
            "materials": [{"storage_uri": "chapter_01.md"}],
        },
    )

    assert response.status_code == 422


def test_knowledge_ingestion_rejects_empty_materials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [],
        },
    )

    assert response.status_code == 422


def test_knowledge_ingestion_rejects_current_directory_storage_uri(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "."}],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert "storage_uri" in payload["message"]


def test_knowledge_ingestion_rejects_storage_root_name_storage_uri(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path / "course_catalogs"))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "course_catalogs"}],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert "storage_uri" in payload["message"]


def test_knowledge_ingestion_calls_ingest_with_catalog_id(tmp_path: Path, monkeypatch) -> None:
    from agent_service.api.v1 import knowledge as knowledge_api
    from agent_service.tools.ingest_knowledge import KnowledgeIngestionResult

    storage_root = tmp_path / "course_catalogs"
    storage_root.mkdir()
    material = storage_root / "chapter_01.md"
    material.write_text("课程资料", encoding="utf-8")
    calls = []

    async def fake_ingest_course_knowledge(path, *, course_id=None):
        calls.append((Path(path), course_id))
        return KnowledgeIngestionResult(course_id=course_id or "", chunk_count=3, duration_seconds=0.1)

    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(storage_root))
    monkeypatch.setattr(knowledge_api, "ingest_course_knowledge", fake_ingest_course_knowledge)

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "chapter_01.md"}],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["code"] == 202
    assert payload["data"]["catalog_id"] == "catalog-1"
    assert payload["data"]["chunk_count"] == 3
    assert payload["data"]["materials"][0]["status"] == "ingested"
    assert calls == [(material.resolve(), "catalog-1")]


def test_knowledge_ingestion_strips_course_catalogs_prefix_before_ingest(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_service.api.v1 import knowledge as knowledge_api
    from agent_service.tools.ingest_knowledge import KnowledgeIngestionResult

    storage_root = tmp_path / "course_catalogs"
    material = storage_root / "catalog-1" / "mat-1" / "intro.md"
    material.parent.mkdir(parents=True)
    material.write_text("课程资料", encoding="utf-8")
    calls = []

    async def fake_ingest_course_knowledge(path, *, course_id=None):
        calls.append((Path(path), course_id))
        return KnowledgeIngestionResult(course_id=course_id or "", chunk_count=2, duration_seconds=0.1)

    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(storage_root))
    monkeypatch.setattr(knowledge_api, "ingest_course_knowledge", fake_ingest_course_knowledge)

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "course_catalogs/catalog-1/mat-1/intro.md"}],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["code"] == 202
    assert payload["data"]["catalog_id"] == "catalog-1"
    assert payload["data"]["chunk_count"] == 2
    assert payload["data"]["materials"][0]["status"] == "ingested"
    assert calls == [(material.resolve(), "catalog-1")]


def test_knowledge_ingestion_marks_missing_material_failed(tmp_path: Path, monkeypatch) -> None:
    storage_root = tmp_path / "course_catalogs"
    storage_root.mkdir()

    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(storage_root))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "catalog-1/mat-1/missing.md"}],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    material_result = payload["data"]["materials"][0]
    assert material_result["status"] == "failed"
    assert "exist" in material_result["error"]
    assert material_result["chunk_count"] == 0


def test_knowledge_ingestion_marks_unsupported_material_type_failed(
    tmp_path: Path, monkeypatch
) -> None:
    storage_root = tmp_path / "course_catalogs"
    material = storage_root / "catalog-1" / "mat-1" / "intro.docx"
    material.parent.mkdir(parents=True)
    material.write_text("课程资料", encoding="utf-8")

    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(storage_root))

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [{"storage_uri": "catalog-1/mat-1/intro.docx"}],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    material_result = payload["data"]["materials"][0]
    assert material_result["status"] == "failed"
    assert "unsupported" in material_result["error"]
    assert material_result["chunk_count"] == 0


def test_knowledge_ingestion_isolates_single_material_ingest_failure(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_service.api.v1 import knowledge as knowledge_api
    from agent_service.tools.ingest_knowledge import KnowledgeIngestionResult

    storage_root = tmp_path / "course_catalogs"
    storage_root.mkdir()
    failed_material = storage_root / "chapter_01.md"
    failed_material.write_text("失败资料", encoding="utf-8")
    successful_material = storage_root / "chapter_02.md"
    successful_material.write_text("成功资料", encoding="utf-8")

    async def fake_ingest_course_knowledge(path, *, course_id=None):
        if Path(path).name == "chapter_01.md":
            raise RuntimeError("boom")
        return KnowledgeIngestionResult(course_id=course_id or "", chunk_count=5, duration_seconds=0.1)

    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(storage_root))
    monkeypatch.setattr(knowledge_api, "ingest_course_knowledge", fake_ingest_course_knowledge)

    response = _client().post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [
                {"storage_uri": "chapter_01.md"},
                {"storage_uri": "chapter_02.md"},
            ],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["data"]["chunk_count"] == 5
    assert payload["data"]["materials"][0]["status"] == "failed"
    assert "boom" in payload["data"]["materials"][0]["error"]
    assert payload["data"]["materials"][1]["status"] == "ingested"
