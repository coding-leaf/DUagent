import os
import sys

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent_test?charset=utf8mb4",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1.catalogs import admin_start_catalog_ingestion, admin_upload_catalog_material
from app.core.config import settings
from app.db.session import async_session_factory, engine, init_db
from app.main import app
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.user import RegistrationCode
from app.schemas.catalog import CourseCatalogMaterialItem


def test_course_catalog_model_has_ingestion_fields():
    columns = CourseCatalog.__table__.columns

    assert "last_ingestion_task_id" in columns
    assert "last_ingestion_status" in columns
    assert "chunk_count" in columns
    assert "last_error" in columns


def test_course_catalog_material_model_has_ingestion_fields():
    columns = CourseCatalogMaterial.__table__.columns

    assert "file_size" in columns
    assert "last_error" in columns
    assert "ingested_at" in columns
    assert "chunk_count" in columns


def test_course_catalog_storage_settings_exist():
    assert hasattr(settings, "COURSE_CATALOG_STORAGE_ROOT")
    assert hasattr(settings, "COURSE_CATALOG_MAX_UPLOAD_BYTES")
    assert settings.COURSE_CATALOG_STORAGE_ROOT
    assert settings.COURSE_CATALOG_MAX_UPLOAD_BYTES > 0


def test_course_catalog_material_schema_has_ingestion_fields():
    material = CourseCatalogMaterialItem(
        id="mat1",
        catalog_id="cat1",
        filename="intro.md",
        source_type="file",
        file_size=12,
        status="uploaded",
        chunk_count=0,
        last_error=None,
        ingested_at=None,
        created_at="2026-06-08T00:00:00",
    )

    assert material.file_size == 12
    assert material.chunk_count == 0
    assert material.last_error is None


def test_course_catalog_ingestion_upgrade_migration_is_idempotent():
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "2026-06-08-extend-course-catalog-ingestion.sql",
    )
    with open(migration_path, encoding="utf-8") as f:
        migration_sql = f.read()

    assert "information_schema.columns" in migration_sql
    for column_name in (
        "last_ingestion_task_id",
        "last_ingestion_status",
        "chunk_count",
        "last_error",
        "file_size",
        "ingested_at",
    ):
        assert f"column_name = '{column_name}'" in migration_sql


def _captcha_answer(question: str) -> str:
    nums = re.findall(r"\d+", question)
    if "+" in question:
        return str(int(nums[0]) + int(nums[1]))
    return str(int(nums[0]) - int(nums[1]))


async def _init_test_db():
    await init_db()
    if "mysql" not in settings.resolved_database_url:
        return

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "2026-06-08-extend-course-catalog-ingestion.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8")
    async with engine.begin() as conn:
        for statement in migration_sql.split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))


async def _register_and_login(client: AsyncClient, role: str):
    code = f"{role}_{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as db:
        db.add(RegistrationCode(code=code, role=role))
        await db.commit()

    email = f"{role}_{uuid.uuid4().hex[:8]}@test.com"
    username = f"{role}_{uuid.uuid4().hex[:8]}"
    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "registration_code": code,
            "email": email,
            "password": "Abc12345",
            "username": username,
            "captcha_token": captcha_data["captcha_token"],
            "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
        },
    )
    assert register.status_code == 201, register.text

    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": captcha_data["captcha_token"],
            "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
        },
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['token']}"}


async def _create_catalog(client: AsyncClient, admin_headers: dict, title: str = "数据结构") -> str:
    create = await client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": title, "description": "Phase B1 test"},
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def _set_catalog_status(catalog_id: str, status: str, knowledge_status: str):
    async with async_session_factory() as db:
        result = await db.execute(select(CourseCatalog).where(CourseCatalog.id == catalog_id))
        catalog = result.scalar_one()
        catalog.status = status
        catalog.knowledge_status = knowledge_status
        await db.commit()


async def _get_material(material_id: str) -> CourseCatalogMaterial:
    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseCatalogMaterial).where(CourseCatalogMaterial.id == material_id)
        )
        return result.scalar_one()


async def _api_test_admin_upload_catalog_material(tmp_path, monkeypatch):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("intro.md", b"# Intro\nBinary tree", "text/markdown")},
            )

            assert response.status_code == 201, response.text
            data = response.json()["data"]
            assert data["filename"] == "intro.md"
            assert data["source_type"] == "file"
            assert data["status"] == "uploaded"
            assert data["file_size"] > 0
            assert data["chunk_count"] == 0
            assert "storage_uri" not in data

            expected_path = tmp_path / "course_catalogs" / catalog_id / data["id"] / "intro.md"
            assert expected_path.exists()
            assert expected_path.read_text(encoding="utf-8").startswith("# Intro")
    finally:
        await engine.dispose()


def test_admin_upload_catalog_material(tmp_path, monkeypatch):
    asyncio.run(_api_test_admin_upload_catalog_material(tmp_path, monkeypatch))


async def _api_test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("slides.pptx", b"bad", "application/octet-stream")},
            )

            assert response.status_code == 400
            assert response.json()["detail"]["message"] == "不支持的资料类型"
    finally:
        await engine.dispose()


def test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch):
    asyncio.run(_api_test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch))


async def _api_test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Ready Catalog")
            await _set_catalog_status(catalog_id, "ready", "ready")

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("delta.txt", b"new material", "text/plain")},
            )
            assert response.status_code == 201, response.text

            status_response = await client.get(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
                headers=admin_headers,
            )
            assert status_response.status_code == 200, status_response.text
            status_data = status_response.json()["data"]
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "dirty"
    finally:
        await engine.dispose()


def test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch):
    asyncio.run(_api_test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch))


async def _api_test_upload_storage_uri_uses_configured_root_name(tmp_path, monkeypatch):
    await _init_test_db()
    storage_root = tmp_path / "catalog_blob_store"
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(storage_root),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Custom Root")

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("intro.md", b"# Intro", "text/markdown")},
            )

            assert response.status_code == 201, response.text
            material_id = response.json()["data"]["id"]
            material = await _get_material(material_id)
            expected_uri = f"{storage_root.name}/{catalog_id}/{material_id}/intro.md"
            assert material.storage_uri == expected_uri
            assert (storage_root / catalog_id / material_id / "intro.md").exists()
    finally:
        await engine.dispose()


def test_upload_storage_uri_uses_configured_root_name(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_storage_uri_uses_configured_root_name(tmp_path, monkeypatch))


class _ChunkOnlyUploadFile:
    filename = "large.md"

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        assert size > 0, "upload must be read in bounded chunks"
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


async def _api_test_upload_reads_in_bounded_chunks_and_removes_oversized_partial(
    tmp_path,
    monkeypatch,
):
    await _init_test_db()
    storage_root = tmp_path / "course_catalogs"
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(storage_root))
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_MAX_UPLOAD_BYTES", 5)
    try:
        async with async_session_factory() as db:
            catalog = CourseCatalog(title="Chunked Upload", status="draft", knowledge_status="draft")
            db.add(catalog)
            await db.commit()
            await db.refresh(catalog)

            upload = _ChunkOnlyUploadFile([b"abcd", b"ef"])
            with pytest.raises(HTTPException) as exc_info:
                await admin_upload_catalog_material(
                    catalog.id,
                    file=upload,  # type: ignore[arg-type]
                    current_user=object(),  # type: ignore[arg-type]
                    db=db,
                )

            assert exc_info.value.status_code == 413
            assert upload.read_sizes
            assert all(size > 0 for size in upload.read_sizes)
            assert not any(storage_root.rglob("*.*"))
    finally:
        await engine.dispose()


def test_upload_reads_in_bounded_chunks_and_removes_oversized_partial(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_reads_in_bounded_chunks_and_removes_oversized_partial(tmp_path, monkeypatch))


async def _api_test_upload_removes_material_dir_for_empty_file(tmp_path, monkeypatch):
    await _init_test_db()
    storage_root = tmp_path / "course_catalogs"
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(storage_root))
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Empty Upload")

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("empty.md", b"", "text/markdown")},
            )

            assert response.status_code == 400
            assert not any(storage_root.rglob("*.*"))
            assert not any(storage_root.glob(f"{catalog_id}/*"))
    finally:
        await engine.dispose()


def test_upload_removes_material_dir_for_empty_file(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_removes_material_dir_for_empty_file(tmp_path, monkeypatch))


class _RowCountResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _FailingFlushDb:
    def __init__(self):
        self.added = []
        self.rolled_back = False

    async def execute(self, *_args, **_kwargs):
        return _RowCountResult(1)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        raise RuntimeError("db flush failed")

    async def rollback(self):
        self.rolled_back = True


async def _api_test_upload_cleans_file_when_db_write_fails(tmp_path, monkeypatch):
    storage_root = tmp_path / "course_catalogs"
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(storage_root))

    async def fake_get_catalog(_db, _catalog_id):
        return SimpleNamespace(
            id="catalog-db-fail",
            status="draft",
            knowledge_status="draft",
        )

    monkeypatch.setattr(
        "app.api.v1.catalogs._get_admin_catalog_or_404",
        fake_get_catalog,
    )
    db = _FailingFlushDb()

    with pytest.raises(RuntimeError, match="db flush failed"):
        await admin_upload_catalog_material(
            "catalog-db-fail",
            file=_ChunkOnlyUploadFile([b"# Intro"]),
            current_user=object(),  # type: ignore[arg-type]
            db=db,  # type: ignore[arg-type]
        )

    assert db.rolled_back is True
    assert db.added
    assert not any(storage_root.rglob("*.*"))
    assert not any(storage_root.glob("catalog-db-fail/*"))


def test_upload_cleans_file_when_db_write_fails(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_cleans_file_when_db_write_fails(tmp_path, monkeypatch))


class _ConcurrentIngestingDb:
    def __init__(self):
        self.added = []
        self.rolled_back = False

    async def execute(self, *_args, **_kwargs):
        return _RowCountResult(0)

    def add(self, obj):
        self.added.append(obj)

    async def rollback(self):
        self.rolled_back = True


async def _api_test_upload_rechecks_ingesting_state_during_catalog_update(tmp_path, monkeypatch):
    storage_root = tmp_path / "course_catalogs"
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(storage_root))

    async def fake_get_catalog(_db, _catalog_id):
        return SimpleNamespace(
            id="catalog-race",
            status="draft",
            knowledge_status="draft",
        )

    monkeypatch.setattr(
        "app.api.v1.catalogs._get_admin_catalog_or_404",
        fake_get_catalog,
    )
    db = _ConcurrentIngestingDb()

    with pytest.raises(HTTPException) as exc_info:
        await admin_upload_catalog_material(
            "catalog-race",
            file=_ChunkOnlyUploadFile([b"# Intro"]),
            current_user=object(),  # type: ignore[arg-type]
            db=db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert db.rolled_back is True
    assert db.added == []
    assert not any(storage_root.rglob("*.*"))
    assert not any(storage_root.glob("catalog-race/*"))


def test_upload_rechecks_ingesting_state_during_catalog_update(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_rechecks_ingesting_state_during_catalog_update(tmp_path, monkeypatch))


class _ReadFailingUploadFile:
    filename = "broken.md"

    def __init__(self):
        self._calls = 0

    async def read(self, size: int = -1) -> bytes:
        self._calls += 1
        if self._calls == 1:
            return b"partial"
        raise RuntimeError("upload read failed")


async def _api_test_upload_cleans_partial_file_when_read_fails(tmp_path, monkeypatch):
    storage_root = tmp_path / "course_catalogs"
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(storage_root))

    async def fake_get_catalog(_db, _catalog_id):
        return SimpleNamespace(
            id="catalog-read-fail",
            status="draft",
            knowledge_status="draft",
        )

    monkeypatch.setattr(
        "app.api.v1.catalogs._get_admin_catalog_or_404",
        fake_get_catalog,
    )

    with pytest.raises(RuntimeError, match="upload read failed"):
        await admin_upload_catalog_material(
            "catalog-read-fail",
            file=_ReadFailingUploadFile(),  # type: ignore[arg-type]
            current_user=object(),  # type: ignore[arg-type]
            db=_ConcurrentIngestingDb(),  # type: ignore[arg-type]
        )

    assert not any(storage_root.rglob("*.*"))
    assert not any(storage_root.glob("catalog-read-fail/*"))


def test_upload_cleans_partial_file_when_read_fails(tmp_path, monkeypatch):
    asyncio.run(_api_test_upload_cleans_partial_file_when_read_fails(tmp_path, monkeypatch))


async def _api_test_json_material_rejects_knowledge_status_ingesting():
    await _init_test_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Knowledge Ingesting")
            await _set_catalog_status(catalog_id, "ready", "ingesting")

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
                headers=admin_headers,
                json={
                    "filename": "blocked.pdf",
                    "source_type": "pdf",
                    "storage_uri": "local://blocked.pdf",
                },
            )

            assert response.status_code == 409
            assert response.json()["detail"]["message"] == "课程资源库正在入库中"

            materials = await client.get(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
                headers=admin_headers,
            )
            assert materials.status_code == 200, materials.text
            assert materials.json()["data"]["materials"] == []
    finally:
        await engine.dispose()


def test_json_material_rejects_knowledge_status_ingesting():
    asyncio.run(_api_test_json_material_rejects_knowledge_status_ingesting())


async def _wait_for_task_status(
    client: AsyncClient,
    headers: dict,
    task_id: str,
    expected: set[str],
):
    for _ in range(20):
        response = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["status"] in expected:
            return data
        await asyncio.sleep(0.05)
    raise AssertionError(f"task {task_id} did not reach {expected}")


async def _get_catalog_status(client: AsyncClient, headers: dict, catalog_id: str) -> dict:
    response = await client.get(
        f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _get_material_from_list(
    client: AsyncClient,
    headers: dict,
    catalog_id: str,
    material_id: str,
) -> dict:
    response = await client.get(
        f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    materials = response.json()["data"]["materials"]
    matches = [material for material in materials if material["id"] == material_id]
    assert matches, f"material {material_id} not found"
    return matches[0]


async def _api_test_start_catalog_ingestion_success(tmp_path, monkeypatch):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)
            upload = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("intro.md", b"# Intro", "text/markdown")},
            )
            material_id = upload.json()["data"]["id"]

            with patch(
                "app.api.v1.catalogs.ingestion_agent_client.post_json",
                new_callable=AsyncMock,
            ) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 2,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{material_id}/intro.md",
                            "status": "ingested",
                            "chunk_count": 2,
                            "error": None,
                        }
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"completed"})
            assert task_data["task_type"] == "course_catalog_ingestion"
            assert task_data["status"] == "completed"
            assert task_data["result"]["catalog_id"] == catalog_id
            assert task_data["result"]["chunk_count"] == 2

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            material = await _get_material_from_list(client, admin_headers, catalog_id, material_id)
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "ready"
            assert status_data["chunk_count"] == 2
            assert status_data["last_ingestion_task_id"] == task_id
            assert material["status"] == "ingested"
            assert material["chunk_count"] == 2
            assert material["ingested_at"] is not None
    finally:
        await engine.dispose()


def test_start_catalog_ingestion_success(tmp_path, monkeypatch):
    asyncio.run(_api_test_start_catalog_ingestion_success(tmp_path, monkeypatch))


async def _api_test_start_catalog_ingestion_without_uploaded_materials_returns_409():
    await _init_test_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                headers=admin_headers,
            )

            assert response.status_code == 409
            assert response.json()["detail"]["message"] == "没有待入库资料"
    finally:
        await engine.dispose()


def test_start_catalog_ingestion_without_uploaded_materials_returns_409():
    asyncio.run(_api_test_start_catalog_ingestion_without_uploaded_materials_returns_409())


class _ScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsAllResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _ConcurrentStartDb:
    def __init__(self):
        self.catalog = SimpleNamespace(
            id="catalog-start-race",
            status="draft",
            knowledge_status="draft",
            is_deleted=False,
        )
        self.material = SimpleNamespace(
            id="material-start-race",
            catalog_id=self.catalog.id,
            storage_uri="course_catalogs/catalog-start-race/material-start-race/intro.md",
            status="uploaded",
            last_error="old error",
        )
        self.added = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement, *_args, **_kwargs):
        statement_text = str(statement)
        if "UPDATE course_catalogs" in statement_text:
            return _RowCountResult(0)
        if "FROM course_catalog_materials" in statement_text:
            return _ScalarsAllResult([self.material])
        return _ScalarOneOrNoneResult(self.catalog)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        raise AssertionError("task must not be flushed when catalog transition loses race")

    async def refresh(self, _obj):
        pass

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class _NoopBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


async def _api_test_start_ingestion_rejects_when_atomic_catalog_transition_loses_race():
    db = _ConcurrentStartDb()
    background_tasks = _NoopBackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await admin_start_catalog_ingestion(
            "catalog-start-race",
            background_tasks=background_tasks,  # type: ignore[arg-type]
            current_user=SimpleNamespace(id="admin-id"),  # type: ignore[arg-type]
            db=db,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["message"] == "课程资源库正在入库中"
    assert db.added == []
    assert db.committed is False
    assert db.rolled_back is True
    assert db.catalog.status == "draft"
    assert db.catalog.knowledge_status == "draft"
    assert db.material.status == "uploaded"
    assert db.material.last_error == "old error"
    assert background_tasks.tasks == []


def test_start_ingestion_rejects_when_atomic_catalog_transition_loses_race():
    asyncio.run(_api_test_start_ingestion_rejects_when_atomic_catalog_transition_loses_race())


async def _api_test_incremental_ingestion_partial_failure_keeps_catalog_ready(
    tmp_path,
    monkeypatch,
):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Incremental Catalog")
            await _set_catalog_status(catalog_id, "ready", "ready")
            upload = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("delta.md", b"# Delta", "text/markdown")},
            )
            material_id = upload.json()["data"]["id"]

            with patch(
                "app.api.v1.catalogs.ingestion_agent_client.post_json",
                new_callable=AsyncMock,
            ) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 0,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{material_id}/delta.md",
                            "status": "failed",
                            "chunk_count": 0,
                            "error": "embedding failed",
                        }
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"failed"})
            assert task_data["status"] == "failed"
            assert task_data["error_code"] == "material_failed"

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            material = await _get_material_from_list(client, admin_headers, catalog_id, material_id)
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "partial"
            assert status_data["last_error"] == "embedding failed"
            assert material["status"] == "failed"
            assert material["last_error"] == "embedding failed"
    finally:
        await engine.dispose()


def test_incremental_ingestion_partial_failure_keeps_catalog_ready(tmp_path, monkeypatch):
    asyncio.run(
        _api_test_incremental_ingestion_partial_failure_keeps_catalog_ready(tmp_path, monkeypatch)
    )


async def _api_test_first_ingestion_partial_success_marks_catalog_ready_partial(
    tmp_path,
    monkeypatch,
):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="First Partial Catalog")
            upload_ok = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("ok.md", b"# OK", "text/markdown")},
            )
            upload_fail = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("bad.md", b"# BAD", "text/markdown")},
            )
            ok_material_id = upload_ok.json()["data"]["id"]
            fail_material_id = upload_fail.json()["data"]["id"]

            with patch(
                "app.api.v1.catalogs.ingestion_agent_client.post_json",
                new_callable=AsyncMock,
            ) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 4,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{ok_material_id}/ok.md",
                            "status": "ingested",
                            "chunk_count": 4,
                            "error": None,
                        },
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{fail_material_id}/bad.md",
                            "status": "failed",
                            "chunk_count": 0,
                            "error": "parse failed",
                        },
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"failed"})
            assert task_data["status"] == "failed"
            assert task_data["error_code"] == "material_failed"

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            ok_material = await _get_material_from_list(
                client,
                admin_headers,
                catalog_id,
                ok_material_id,
            )
            fail_material = await _get_material_from_list(
                client,
                admin_headers,
                catalog_id,
                fail_material_id,
            )
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "partial"
            assert status_data["chunk_count"] == 4
            assert status_data["last_error"] == "parse failed"
            assert ok_material["status"] == "ingested"
            assert fail_material["status"] == "failed"
    finally:
        await engine.dispose()


def test_first_ingestion_partial_success_marks_catalog_ready_partial(tmp_path, monkeypatch):
    asyncio.run(
        _api_test_first_ingestion_partial_success_marks_catalog_ready_partial(tmp_path, monkeypatch)
    )


async def _api_test_catalog_ingestion_unexpected_exception_recovers_state(
    tmp_path,
    monkeypatch,
    *,
    initial: bool,
):
    await _init_test_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            title = "Initial Malformed" if initial else "Incremental Malformed"
            catalog_id = await _create_catalog(client, admin_headers, title=title)
            if not initial:
                await _set_catalog_status(catalog_id, "ready", "ready")
            upload = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("malformed.md", b"# Bad Chunk", "text/markdown")},
            )
            assert upload.status_code == 201, upload.text
            material_id = upload.json()["data"]["id"]

            with patch(
                "app.api.v1.catalogs.ingestion_agent_client.post_json",
                new_callable=AsyncMock,
            ) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 1,
                    "materials": [
                        {
                            "storage_uri": (
                                f"course_catalogs/{catalog_id}/{material_id}/malformed.md"
                            ),
                            "status": "ingested",
                            "chunk_count": "bad",
                            "error": None,
                        }
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"failed"})
            assert task_data["status"] == "failed"
            assert task_data["error_code"] == "unexpected_error"
            assert "invalid literal" in task_data["error_message"]

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            material = await _get_material_from_list(client, admin_headers, catalog_id, material_id)
            assert status_data["status"] == ("failed" if initial else "ready")
            assert status_data["knowledge_status"] == ("failed" if initial else "partial")
            assert status_data["last_ingestion_status"] == "failed"
            assert "invalid literal" in status_data["last_error"]
            assert material["status"] == "failed"
            assert "invalid literal" in material["last_error"]
    finally:
        await engine.dispose()


def test_initial_catalog_ingestion_unexpected_exception_marks_catalog_failed(
    tmp_path,
    monkeypatch,
):
    asyncio.run(
        _api_test_catalog_ingestion_unexpected_exception_recovers_state(
            tmp_path,
            monkeypatch,
            initial=True,
        )
    )


def test_incremental_catalog_ingestion_unexpected_exception_keeps_catalog_ready_partial(
    tmp_path,
    monkeypatch,
):
    asyncio.run(
        _api_test_catalog_ingestion_unexpected_exception_recovers_state(
            tmp_path,
            monkeypatch,
            initial=False,
        )
    )
