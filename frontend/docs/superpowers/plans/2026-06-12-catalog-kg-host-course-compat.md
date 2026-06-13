# Catalog KG Host Course Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admins to generate and view knowledge graphs for a course catalog even when no teaching class is bound, by introducing a hidden host course used only for KG persistence.

**Architecture:** Keep `CourseKnowledgeGraph` and existing KG services keyed by `course_id`, but add a catalog-level `kg_host_course_id` pointer and a helper that creates or reuses a hidden host course on demand. Switch admin catalog KG status/generation endpoints to resolve that host course instead of requiring a bound `CourseOffering`, and ensure hidden host courses never leak into teacher/student course flows.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, MySQL migrations, pytest, existing frontend React admin drawer

---

### Task 1: Add catalog host-course persistence

**Files:**
- Modify: `backend/app/models/catalog.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`
- Create: `backend/migrations/2026-06-12-add-catalog-kg-host-course-id.sql`

- [ ] **Step 1: Write the failing schema/model test**

```python
async def test_seed_ready_catalog_can_store_kg_host_course_id():
    await _reset_db()
    catalog_id = await _seed_ready_catalog()

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        catalog.kg_host_course_id = "host-course-1"
        await db.commit()
        await db.refresh(catalog)

    assert catalog.kg_host_course_id == "host-course-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_seed_ready_catalog_can_store_kg_host_course_id -q -p no:cacheprovider`

Expected: FAIL with SQLAlchemy model attribute or database column missing for `kg_host_course_id`

- [ ] **Step 3: Add the model field and migration**

```python
class CourseCatalog(Base):
    __tablename__ = "course_catalogs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    knowledge_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    material_count: Mapped[int] = mapped_column(Integer, default=0)
    last_ingestion_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_ingestion_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kg_host_course_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("courses.id"), nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

```sql
ALTER TABLE course_catalogs
    ADD COLUMN kg_host_course_id VARCHAR(32) NULL AFTER last_error,
    ADD INDEX idx_course_catalog_kg_host_course_id (kg_host_course_id),
    ADD CONSTRAINT fk_course_catalog_kg_host_course
        FOREIGN KEY (kg_host_course_id) REFERENCES courses(id);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_seed_ready_catalog_can_store_kg_host_course_id -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/catalog.py backend/migrations/2026-06-12-add-catalog-kg-host-course-id.sql backend/tests/test_admin_catalog_kg_generation.py
git commit -m "增加资源库KG宿主课字段"
```

### Task 2: Create or reuse a hidden host course for each catalog

**Files:**
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`

- [ ] **Step 1: Write the failing host-course creation test**

```python
@pytest.mark.asyncio
async def test_catalog_kg_generation_creates_hidden_host_course_when_no_offering():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog(status="ready", knowledge_status="ready", chunk_count=5)

    with patch("app.api.v1.catalogs.generate_knowledge_graph_version", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "course_id": "host-course-generated",
            "graph_id": "graph-1",
            "version": 1,
            "node_count": 1,
            "edge_count": 0,
            "source_type": "catalog_chunks",
            "generation_strategy": "catalog_chunks_llm",
            "metrics": {},
            "activated": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={},
            )

    assert response.status_code == 202, response.text

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        host_course = await db.get(Course, catalog.kg_host_course_id)

    assert catalog.kg_host_course_id is not None
    assert host_course is not None
    assert host_course.teacher_id == "admin-admin-gen"
    assert host_course.name.startswith("[KG HOST]")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_creates_hidden_host_course_when_no_offering -q -p no:cacheprovider`

Expected: FAIL with `40915` or missing `kg_host_course_id`

- [ ] **Step 3: Add the helper and minimal implementation**

```python
async def _get_or_create_catalog_kg_host_course(
    db: AsyncSession,
    catalog: CourseCatalog,
    *,
    actor_user_id: str,
) -> Course:
    if catalog.kg_host_course_id:
        existing = await db.get(Course, catalog.kg_host_course_id)
        if existing is not None and not existing.is_deleted:
            return existing

    host_course = Course(
        name=f"[KG HOST] {catalog.title}",
        description=f"System host course for catalog {catalog.id} knowledge graphs",
        course_code=f"KGH{catalog.id[:8].upper()}",
        teacher_id=actor_user_id,
    )
    db.add(host_course)
    await db.flush()
    catalog.kg_host_course_id = host_course.id
    await db.flush()
    return host_course
```

```python
catalog = await _get_admin_catalog_or_404(db, catalog_id)
host_course = await _get_or_create_catalog_kg_host_course(
    db,
    catalog,
    actor_user_id=current_user.id,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_creates_hidden_host_course_when_no_offering -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/tests/test_admin_catalog_kg_generation.py
git commit -m "增加资源库KG宿主课创建逻辑"
```

### Task 3: Switch admin KG generation to host course instead of offering gate

**Files:**
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`

- [ ] **Step 1: Write the failing endpoint behavior test**

```python
@pytest.mark.asyncio
async def test_catalog_kg_generation_without_offering_returns_202_not_40915():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog(status="ready", knowledge_status="ready", chunk_count=5)

    with patch("app.api.v1.catalogs.generate_knowledge_graph_version", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "course_id": "host-course-generated",
            "graph_id": "graph-1",
            "version": 1,
            "node_count": 1,
            "edge_count": 0,
            "source_type": "catalog_chunks",
            "generation_strategy": "catalog_chunks_llm",
            "metrics": {},
            "activated": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={},
            )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["catalog_id"] == catalog_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_without_offering_returns_202_not_40915 -q -p no:cacheprovider`

Expected: FAIL with `409 Conflict` and `课程资源库尚未绑定教学班`

- [ ] **Step 3: Replace offering gate with host-course resolution**

```python
catalog = await _get_admin_catalog_or_404(db, catalog_id)
host_course = await _get_or_create_catalog_kg_host_course(
    db,
    catalog,
    actor_user_id=current_user.id,
)

task_result = {
    "catalog_id": catalog.id,
    "course_id": host_course.id,
    "source_type": req.source_type,
    "activate": req.activate,
}

task = AsyncTask(
    task_type="kg_generation",
    status="processing",
    progress=10,
    user_id=current_user.id,
    course_id=host_course.id,
    result=task_result,
)
```

- [ ] **Step 4: Run targeted tests to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_without_offering_returns_202_not_40915 tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_creates_hidden_host_course_when_no_offering -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/tests/test_admin_catalog_kg_generation.py
git commit -m "移除资源库KG绑定班级前置限制"
```

### Task 4: Switch admin KG status reads to host course

**Files:**
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`

- [ ] **Step 1: Write the failing status-read test**

```python
@pytest.mark.asyncio
async def test_catalog_kg_status_reads_active_graph_from_host_course():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog(status="ready", knowledge_status="ready", chunk_count=5)

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        host_course = Course(
            id="host-course-status",
            name="[KG HOST] Catalog",
            course_code="KGHSTATUS",
            teacher_id="admin-admin-gen",
        )
        db.add(host_course)
        await db.flush()
        catalog.kg_host_course_id = host_course.id
        db.add(
            CourseKnowledgeGraph(
                id="kg-host-status",
                course_id=host_course.id,
                version=1,
                is_active=True,
                source_type="manual_import",
                generation_strategy="manual_kg_json",
                nodes=[{"id": "n1", "name": "指针", "chapter": "第六章"}],
                edges=[],
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["course_id"] == "host-course-status"
    assert response.json()["data"]["active_graph"]["graph_id"] == "kg-host-status"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_status_reads_active_graph_from_host_course -q -p no:cacheprovider`

Expected: FAIL because endpoint still tries `_first_catalog_offering(...)`

- [ ] **Step 3: Update the status endpoint**

```python
catalog = await _get_admin_catalog_or_404(db, catalog_id)
host_course = await _get_or_create_catalog_kg_host_course(
    db,
    catalog,
    actor_user_id=current_user.id,
)
graph = await get_active_knowledge_graph(db, host_course.id)

return {
    "code": 200,
    "message": "success",
    "data": {
        "catalog_id": catalog.id,
        "course_id": host_course.id,
        "active_graph": _knowledge_graph_summary(graph) if graph else None,
        "last_generation_task": _knowledge_graph_task_summary(task) if task else None,
    },
}
```

- [ ] **Step 4: Run targeted tests to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_status_reads_active_graph_from_host_course tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_without_offering_returns_202_not_40915 -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/tests/test_admin_catalog_kg_generation.py
git commit -m "改为按宿主课读取资源库KG状态"
```

### Task 5: Keep hidden host courses out of real course flows

**Files:**
- Modify: `backend/app/api/v1/courses.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`
- Modify: `backend/tests/test_courses_async.py`

- [ ] **Step 1: Write the failing visibility test**

```python
@pytest.mark.asyncio
async def test_hidden_kg_host_course_does_not_appear_in_courses_list():
    await _reset_db()
    await _seed_user("teacher-hidden", "teacher")
    await _seed_user("admin-hidden", "admin")

    async with async_session_factory() as db:
        db.add(
            Course(
                id="host-hidden-course",
                name="[KG HOST] Hidden",
                course_code="KGHHIDDEN",
                teacher_id="admin-hidden",
                description="System host course for catalog hidden",
            )
        )
        db.add(
            Course(
                id="real-course-visible",
                name="Visible Course",
                course_code="VISIBLE1",
                teacher_id="teacher-hidden",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/courses",
            headers=_auth_headers("teacher-hidden", "teacher"),
        )

    assert response.status_code == 200, response.text
    course_ids = [item["id"] for item in response.json()["data"]["courses"]]
    assert "real-course-visible" in course_ids
    assert "host-hidden-course" not in course_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_hidden_kg_host_course_does_not_appear_in_courses_list -q -p no:cacheprovider`

Expected: FAIL because host course is still visible

- [ ] **Step 3: Add a minimal hidden-host filter**

```python
def _is_catalog_kg_host_course_expr():
    return Course.description.like("System host course for catalog %")
```

```python
select(Course).where(
    Course.is_deleted == False,
    ~_is_catalog_kg_host_course_expr(),
    ...
)
```

- [ ] **Step 4: Run targeted tests to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_hidden_kg_host_course_does_not_appear_in_courses_list tests/test_courses_async.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/courses.py backend/tests/test_admin_catalog_kg_generation.py backend/tests/test_courses_async.py
git commit -m "隔离资源库KG宿主课不进课程列表"
```

### Task 6: Update admin drawer copy to resource-catalog wording

**Files:**
- Modify: `frontend/src/components/admin/CourseCatalogDrawer.jsx`
- Test: `frontend/e2e/specs.spec.js`

- [ ] **Step 1: Write the failing UI assertion**

```javascript
test('Admin catalog drawer KG section uses catalog wording instead of class binding gate', async ({ page }) => {
  await page.route('**/api/v1/admin/course-catalogs/catalog-1/knowledge-graphs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        message: 'success',
        data: {
          catalog_id: 'catalog-1',
          course_id: 'host-course-1',
          active_graph: null,
          last_generation_task: null
        }
      })
    });
  });

  await expect(page.getByText('当前资源库暂无 active 知识图谱')).toBeVisible();
  await expect(page.getByText('当前尚未被教学班使用')).toHaveCount(0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:e2e -- e2e/specs.spec.js -g "Admin catalog drawer KG section uses catalog wording instead of class binding gate"`

Expected: FAIL because old wording still appears

- [ ] **Step 3: Update the drawer copy**

```jsx
<p className="mt-1 text-xs text-slate-500">
  {knowledgeGraphStatus?.active_graph
    ? '当前显示的是该资源库的 active 知识图谱'
    : '当前资源库暂无 active 知识图谱'}
</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:e2e -- e2e/specs.spec.js -g "Admin catalog drawer KG section uses catalog wording instead of class binding gate"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/CourseCatalogDrawer.jsx frontend/e2e/specs.spec.js
git commit -m "调整资源库KG区文案"
```

### Task 7: Run full targeted regression and update progress docs

**Files:**
- Modify: `frontend/WORKFLOW.md`
- Modify: `frontend/docs/feature-ledger.md`

- [ ] **Step 1: Write the workflow entry and ledger update**

```md
- 2026-06-12：Admin 资源库 KG 支持未绑定教学班场景：
  - Backend 为 `CourseCatalog` 新增 `kg_host_course_id`，管理员 KG generation/status 统一改走隐藏宿主课，不再依赖第一个绑定教学班。
  - 宿主课只用于 `course_knowledge_graphs` 与 KG task 承载，课程列表显式过滤，不暴露给教师/学生。
  - Admin 抽屉 KG 区文案改为资源库视角，未绑定教学班的新资源库可直接刷新图谱。
```

- [ ] **Step 2: Run backend targeted regression**

Run: `../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py tests/test_courses_async.py tests/test_node_resources.py -q -p no:cacheprovider`

Expected: PASS

- [ ] **Step 3: Run frontend targeted regression**

Run: `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog KG generation|Admin catalog drawer KG section uses catalog wording instead of class binding gate"`

Expected: PASS

- [ ] **Step 4: Run frontend quality checks**

Run: `npm run lint`

Expected: PASS

Run: `npm run build`

Expected: PASS, existing Vite chunk size warning may remain

- [ ] **Step 5: Commit**

```bash
git add frontend/WORKFLOW.md frontend/docs/feature-ledger.md
git commit -m "记录资源库KG宿主课过渡方案"
```

## Self-Review

- Spec coverage:
  - 未绑定教学班也能生成 KG：Task 2-3
  - 未绑定教学班也能查看 KG：Task 4
  - 宿主课长期过渡方案：Task 1-5
  - 宿主课不可泄漏到真实业务：Task 5
  - Admin 文案改为资源库视角：Task 6
  - 测试与进度同步：Task 7
- Placeholder scan:
  - 已避免 `TODO/TBD/类似任务N`
  - 每个任务都给出文件、测试、命令和最小代码片段
- Type consistency:
  - 统一使用 `kg_host_course_id`
  - 统一使用 `_get_or_create_catalog_kg_host_course(...)`
  - 统一将管理员 KG 接口切到 `host_course.id`
