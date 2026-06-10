# KG Versioning and Route A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add KG version / rollback infrastructure first, then implement the minimal Route A generation gate that prunes outline KG nodes without body chunk support.

**Architecture:** Keep `course_knowledge_graphs` as the storage table, but turn it from one row per course into many versions per course with exactly one active version. Reuse the existing body grounding probe logic as the generation-time quality gate: generate candidate nodes from the outline, score each node against non-TOC body chunks, prune unsupported nodes, then save a new KG version with metrics.

**Tech Stack:** FastAPI backend, SQLAlchemy async ORM, MySQL, Qdrant, existing `tools/generate_knowledge_graph.py`, existing pytest suite.

---

## Fixed Success Criterion

Before any Route A code is accepted, this criterion is fixed:

```text
After excluding TOC-like chunks, the share of KG nodes with body_top1_score >= 0.70
must improve from the current 21.6% to >= 70%.
```

This criterion is the route-A success line. Do not replace it with a subjective review after the implementation.

## File Map

- Modify: `../backend/schema.sql`
  - Add KG version fields and replace the current one-course unique index.
- Create: `../backend/migrations/2026-06-10-version-course-knowledge-graphs.sql`
  - MySQL migration for existing environments.
- Modify: `../backend/app/models/others.py`
  - Add ORM fields for KG versioning.
- Create: `../backend/app/services/course_knowledge_graphs.py`
  - Centralize active KG lookup, create-version, activate-version, and rollback behavior.
- Modify: `../backend/app/api/v1/learning_path.py`
  - Replace direct KG queries with active KG lookup.
- Modify: `../backend/app/services/kg_resource_alignment_probe.py`
  - Replace direct KG query helper with active KG lookup.
- Modify: `../backend/tools/generate_knowledge_graph.py`
  - Save new versions instead of overwriting and add Route A body grounding mode.
- Modify: `../backend/tools/import_knowledge_graph.py`
  - Save manual imports as new versions and support activation by version/id.
- Create: `../backend/app/services/kg_body_grounding.py`
  - Shared body-chunk scoring and pruning logic.
- Modify: `../backend/tests/test_generate_kg.py`
  - Add unit tests for pruning and version metadata.
- Create: `../backend/tests/test_course_knowledge_graph_versions.py`
  - Add MySQL-backed tests for version creation, active lookup, and rollback.
- Create: `../backend/tests/test_kg_body_grounding.py`
  - Add unit tests for TOC exclusion, threshold filtering, metrics, and edge pruning.
- Modify: `WORKFLOW.md`
  - Record the implementation and verification results.
- Modify: `docs/feature-ledger.md`
  - Update next-step status after implementation.

## Task 1: Add KG Version Schema and ORM Fields

**Files:**
- Modify: `../backend/schema.sql`
- Create: `../backend/migrations/2026-06-10-version-course-knowledge-graphs.sql`
- Modify: `../backend/app/models/others.py`
- Test: `../backend/tests/test_course_knowledge_graph_versions.py`

- [ ] **Step 1: Write the failing MySQL-backed version model test**

Create `../backend/tests/test_course_knowledge_graph_versions.py`:

```python
import os
import sys

import pytest
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")
if not os.environ["DATABASE_URL"].startswith("mysql+"):
    pytest.skip("KG version tests require TEST_DATABASE_URL with MySQL", allow_module_level=True)

from app.db.session import async_session_factory, engine, init_db
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph
from app.services.course_knowledge_graphs import (
    activate_knowledge_graph_version,
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)


@pytest.mark.asyncio
async def test_create_versions_keeps_one_active_graph():
    await init_db()
    course = Course(name="KG Version Course", description="")
    async with async_session_factory() as db:
        db.add(course)
        await db.commit()
        await db.refresh(course)
        course_id = course.id

        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n1", "name": "变量", "chapter": "第1章"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="legacy_outline",
            metrics={"body_support_pass_ratio": 0.216},
            activate=True,
        )
        second = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n2", "name": "函数", "chapter": "第5章"}],
            edges=[],
            source_type="route_a_body_grounded",
            generation_strategy="route_a_prune_unsupported",
            metrics={"body_support_pass_ratio": 0.72},
            activate=True,
            parent_graph_id=first.id,
        )
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)
        assert active.id == second.id
        assert active.version == 2
        assert active.is_active is True
        assert active.parent_graph_id == first.id

        rows = (
            await db.execute(
                select(CourseKnowledgeGraph).where(CourseKnowledgeGraph.course_id == course_id)
            )
        ).scalars().all()
        assert len(rows) == 2
        assert sum(1 for row in rows if row.is_active) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_activate_knowledge_graph_version_rolls_back_active_graph():
    await init_db()
    course = Course(name="KG Rollback Course", description="")
    async with async_session_factory() as db:
        db.add(course)
        await db.commit()
        await db.refresh(course)
        course_id = course.id

        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n1", "name": "变量", "chapter": "第1章"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="legacy_outline",
            metrics={},
            activate=True,
        )
        await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n2", "name": "函数", "chapter": "第5章"}],
            edges=[],
            source_type="route_a_body_grounded",
            generation_strategy="route_a_prune_unsupported",
            metrics={},
            activate=True,
        )

        rolled_back = await activate_knowledge_graph_version(db, course_id=course_id, graph_id=first.id)
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)
        assert rolled_back.id == first.id
        assert active.id == first.id
        assert active.is_active is True

    await engine.dispose()
```

- [ ] **Step 2: Run the failing test**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: FAIL because `app.services.course_knowledge_graphs` and new model fields do not exist.

- [ ] **Step 3: Update SQL schema**

In `../backend/schema.sql`, replace the existing `course_knowledge_graphs` definition with:

```sql
CREATE TABLE course_knowledge_graphs (
    id                  VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '图谱记录ID',
    course_id           VARCHAR(32)   NOT NULL COMMENT '课程ID',
    version             INT           NOT NULL DEFAULT 1 COMMENT '同一课程内的图谱版本',
    is_active           TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否为当前生效版本',
    source_type         VARCHAR(40)   NOT NULL DEFAULT 'manual_import' COMMENT '来源类型',
    generation_strategy VARCHAR(60)   NOT NULL DEFAULT 'legacy_outline' COMMENT '生成策略',
    metrics             JSON          DEFAULT NULL COMMENT '生成和验收指标',
    parent_graph_id     VARCHAR(32)   DEFAULT NULL COMMENT '来源图谱版本ID',
    nodes               JSON          NOT NULL COMMENT '知识图谱节点 [{id, name, chapter}]',
    edges               JSON          NOT NULL COMMENT '前置依赖边 [{from, to}]',
    create_time         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by           VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by           VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted          TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    UNIQUE INDEX uk_course_version (course_id, version),
    INDEX idx_course_active (course_id, is_active, is_deleted),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_ckg_course FOREIGN KEY (course_id) REFERENCES courses(id),
    CONSTRAINT fk_ckg_parent FOREIGN KEY (parent_graph_id) REFERENCES course_knowledge_graphs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课程静态知识图谱表';
```

- [ ] **Step 4: Add the MySQL migration**

Create `../backend/migrations/2026-06-10-version-course-knowledge-graphs.sql`:

```sql
ALTER TABLE course_knowledge_graphs
    DROP INDEX uk_course,
    ADD COLUMN version INT NOT NULL DEFAULT 1 COMMENT '同一课程内的图谱版本' AFTER course_id,
    ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否为当前生效版本' AFTER version,
    ADD COLUMN source_type VARCHAR(40) NOT NULL DEFAULT 'manual_import' COMMENT '来源类型' AFTER is_active,
    ADD COLUMN generation_strategy VARCHAR(60) NOT NULL DEFAULT 'legacy_outline' COMMENT '生成策略' AFTER source_type,
    ADD COLUMN metrics JSON DEFAULT NULL COMMENT '生成和验收指标' AFTER generation_strategy,
    ADD COLUMN parent_graph_id VARCHAR(32) DEFAULT NULL COMMENT '来源图谱版本ID' AFTER metrics,
    ADD UNIQUE INDEX uk_course_version (course_id, version),
    ADD INDEX idx_course_active (course_id, is_active, is_deleted),
    ADD CONSTRAINT fk_ckg_parent FOREIGN KEY (parent_graph_id) REFERENCES course_knowledge_graphs(id);
```

- [ ] **Step 5: Update ORM fields**

Modify `CourseKnowledgeGraph` in `../backend/app/models/others.py`:

```python
class CourseKnowledgeGraph(Base):
    """课程静态知识图谱 — Backend 调用 Agent /learning-path/generate 时传入 knowledge_graph.nodes/edges。"""
    __tablename__ = "course_knowledge_graphs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="manual_import", nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(60), default="legacy_outline", nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_graph_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("course_knowledge_graphs.id"),
        nullable=True,
    )
    nodes: Mapped[dict] = mapped_column(JSON, nullable=False)
    edges: Mapped[dict] = mapped_column(JSON, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

Also add `Integer` to the SQLAlchemy imports if it is not already imported in that file.

- [ ] **Step 6: Run the test again**

Run:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: still FAIL until Task 2 creates the service functions.

## Task 2: Centralize Active KG Version Service

**Files:**
- Create: `../backend/app/services/course_knowledge_graphs.py`
- Modify: `../backend/app/api/v1/learning_path.py`
- Modify: `../backend/app/services/kg_resource_alignment_probe.py`
- Test: `../backend/tests/test_course_knowledge_graph_versions.py`

- [ ] **Step 1: Implement the service**

Create `../backend/app/services/course_knowledge_graphs.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import CourseKnowledgeGraph


async def get_active_knowledge_graph(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    result = await db.execute(
        select(CourseKnowledgeGraph)
        .where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_active.is_(True),
            CourseKnowledgeGraph.is_deleted.is_(False),
        )
        .order_by(CourseKnowledgeGraph.version.desc(), CourseKnowledgeGraph.update_time.desc())
    )
    return result.scalars().first()


async def next_knowledge_graph_version(db: AsyncSession, course_id: str) -> int:
    result = await db.execute(
        select(func.max(CourseKnowledgeGraph.version)).where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_deleted.is_(False),
        )
    )
    return int(result.scalar() or 0) + 1


async def create_knowledge_graph_version(
    db: AsyncSession,
    *,
    course_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    source_type: str,
    generation_strategy: str,
    metrics: dict[str, Any] | None = None,
    activate: bool = True,
    parent_graph_id: str | None = None,
) -> CourseKnowledgeGraph:
    version = await next_knowledge_graph_version(db, course_id)
    if activate:
        await db.execute(
            update(CourseKnowledgeGraph)
            .where(
                CourseKnowledgeGraph.course_id == course_id,
                CourseKnowledgeGraph.is_deleted.is_(False),
            )
            .values(is_active=False, update_time=datetime.now(timezone.utc))
        )
    graph = CourseKnowledgeGraph(
        course_id=course_id,
        version=version,
        is_active=activate,
        source_type=source_type,
        generation_strategy=generation_strategy,
        metrics=metrics or {},
        parent_graph_id=parent_graph_id,
        nodes=nodes,
        edges=edges,
    )
    db.add(graph)
    await db.flush()
    return graph


async def activate_knowledge_graph_version(
    db: AsyncSession,
    *,
    course_id: str,
    graph_id: str | None = None,
    version: int | None = None,
) -> CourseKnowledgeGraph:
    if not graph_id and version is None:
        raise ValueError("graph_id or version is required")

    query = select(CourseKnowledgeGraph).where(
        CourseKnowledgeGraph.course_id == course_id,
        CourseKnowledgeGraph.is_deleted.is_(False),
    )
    if graph_id:
        query = query.where(CourseKnowledgeGraph.id == graph_id)
    else:
        query = query.where(CourseKnowledgeGraph.version == version)

    result = await db.execute(query)
    target = result.scalars().first()
    if target is None:
        raise ValueError("knowledge graph version not found")

    await db.execute(
        update(CourseKnowledgeGraph)
        .where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_deleted.is_(False),
        )
        .values(is_active=False, update_time=datetime.now(timezone.utc))
    )
    target.is_active = True
    target.update_time = datetime.now(timezone.utc)
    await db.flush()
    return target
```

- [ ] **Step 2: Use active KG in LearningPath refresh payload**

In `../backend/app/api/v1/learning_path.py`, add:

```python
from app.services.course_knowledge_graphs import get_active_knowledge_graph
```

Replace the direct KG select in `_build_learning_path_payload` with:

```python
    kg = await get_active_knowledge_graph(db, course_id)
    if kg:
        payload["knowledge_graph"] = {"nodes": kg.nodes or [], "edges": kg.edges or []}
    else:
        payload["knowledge_graph"] = {"nodes": [], "edges": []}
```

- [ ] **Step 3: Use active KG in node resource lookup**

In `../backend/app/api/v1/learning_path.py`, replace the direct KG select in the node resource endpoint with:

```python
    kg = await get_active_knowledge_graph(db, course_id)
    if kg and kg.nodes:
        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        for kg_node in kg_nodes:
            if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                chapter = kg_node.get("chapter", "")
                break
```

- [ ] **Step 4: Use active KG in the KG-resource alignment probe**

In `../backend/app/services/kg_resource_alignment_probe.py`, import:

```python
from app.services.course_knowledge_graphs import get_active_knowledge_graph
```

Replace `_knowledge_graph` body with:

```python
async def _knowledge_graph(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    return await get_active_knowledge_graph(db, course_id)
```

- [ ] **Step 5: Run version and node-resource tests**

Run:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py tests/test_node_resources.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1-2**

Run:

```bash
git add app/models/others.py app/services/course_knowledge_graphs.py app/api/v1/learning_path.py app/services/kg_resource_alignment_probe.py schema.sql migrations/2026-06-10-version-course-knowledge-graphs.sql tests/test_course_knowledge_graph_versions.py
git commit -m "增加KG版本和回滚基础设施"
```

## Task 3: Change KG Tools from Upsert to Version Creation

**Files:**
- Modify: `../backend/tools/generate_knowledge_graph.py`
- Modify: `../backend/tools/import_knowledge_graph.py`
- Modify: `../backend/tests/test_generate_kg.py`
- Test: `../backend/tests/test_generate_kg.py`

- [ ] **Step 1: Add a unit test for version-result formatting**

Append to `../backend/tests/test_generate_kg.py`:

```python
def test_build_import_result_uses_version_metadata():
    from tools.generate_knowledge_graph import build_import_result

    result = build_import_result(
        course_id="course1",
        graph_id="graph1",
        version=3,
        nodes=[{"id": "n1", "name": "变量", "chapter": "第1章"}],
        edges=[],
        source_type="route_a_body_grounded",
        generation_strategy="route_a_prune_unsupported",
        metrics={"body_support_pass_ratio": 0.72},
        activated=True,
    )

    assert result == {
        "course_id": "course1",
        "graph_id": "graph1",
        "version": 3,
        "node_count": 1,
        "edge_count": 0,
        "source_type": "route_a_body_grounded",
        "generation_strategy": "route_a_prune_unsupported",
        "metrics": {"body_support_pass_ratio": 0.72},
        "activated": True,
    }
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
../.venv/bin/python -m pytest tests/test_generate_kg.py::test_build_import_result_uses_version_metadata -q
```

Expected: FAIL because `build_import_result` does not exist.

- [ ] **Step 3: Implement version creation in `generate_knowledge_graph.py`**

In `../backend/tools/generate_knowledge_graph.py`, replace the direct upsert helper with:

```python
from app.services.course_knowledge_graphs import create_knowledge_graph_version, get_active_knowledge_graph
```

Add:

```python
def build_import_result(
    *,
    course_id: str,
    graph_id: str,
    version: int,
    nodes: list,
    edges: list,
    source_type: str,
    generation_strategy: str,
    metrics: dict,
    activated: bool,
) -> dict:
    return {
        "course_id": course_id,
        "graph_id": graph_id,
        "version": version,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "source_type": source_type,
        "generation_strategy": generation_strategy,
        "metrics": metrics,
        "activated": activated,
    }
```

Replace `upsert_knowledge_graph` with:

```python
async def save_knowledge_graph_version(
    course_id: str,
    nodes: list,
    edges: list,
    *,
    source_type: str = "outline_llm",
    generation_strategy: str = "legacy_outline",
    metrics: dict | None = None,
    activate: bool = True,
) -> dict:
    async with async_session_factory() as db:
        parent = await get_active_knowledge_graph(db, course_id)
        graph = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
            generation_strategy=generation_strategy,
            metrics=metrics or {},
            activate=activate,
            parent_graph_id=parent.id if parent else None,
        )
        await db.commit()
        return build_import_result(
            course_id=course_id,
            graph_id=graph.id,
            version=graph.version,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
            generation_strategy=generation_strategy,
            metrics=metrics or {},
            activated=activate,
        )
```

Update `main_async()` to call `save_knowledge_graph_version(...)` and print `Created version {result["version"]}` instead of `Updated/Created`.

- [ ] **Step 4: Update manual import tool**

In `../backend/tools/import_knowledge_graph.py`, replace `upsert_knowledge_graph` with `save_knowledge_graph_version` equivalent:

```python
from app.services.course_knowledge_graphs import (
    activate_knowledge_graph_version,
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)
```

Add CLI args:

```python
parser.add_argument("--activate-version", type=int, help="只激活指定 KG version，不导入新 JSON")
parser.add_argument("--activate-id", help="只激活指定 KG graph id，不导入新 JSON")
parser.add_argument("--no-activate", action="store_true", help="导入为历史版本但不设为 active")
```

Behavior:

```python
if args.activate_version or args.activate_id:
    result = asyncio.run(activate_existing(args.course_id, args.activate_id, args.activate_version))
    print(f"activated KG for course {args.course_id}: version {result['version']} graph {result['graph_id']}")
    return
```

For JSON import, create a new version with:

```python
source_type="manual_import"
generation_strategy="legacy_outline"
activate=not args.no_activate
```

- [ ] **Step 5: Run tests**

Run:

```bash
../.venv/bin/python -m pytest tests/test_generate_kg.py -q
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add tools/generate_knowledge_graph.py tools/import_knowledge_graph.py tests/test_generate_kg.py
git commit -m "改造KG导入工具保留历史版本"
```

## Task 4: Implement Route A Body Grounding Prune Gate

**Files:**
- Create: `../backend/app/services/kg_body_grounding.py`
- Modify: `../backend/tools/generate_knowledge_graph.py`
- Create: `../backend/tests/test_kg_body_grounding.py`
- Test: `../backend/tests/test_kg_body_grounding.py`

- [ ] **Step 1: Write unit tests for pruning and metrics**

Create `../backend/tests/test_kg_body_grounding.py`:

```python
from app.services.kg_body_grounding import (
    GroundingMatch,
    filter_supported_knowledge_graph,
    is_toc_like_chunk,
)


def test_is_toc_like_chunk_detects_directory_pages():
    assert is_toc_like_chunk("目录\n第1章 C语言概述 1\n第2章 数据类型 8")
    assert is_toc_like_chunk("Contents\nChapter 1 Introduction\nChapter 2 Variables")
    assert not is_toc_like_chunk("变量用于保存程序运行中的数据，变量必须先定义后使用。")


def test_filter_supported_knowledge_graph_prunes_nodes_and_dangling_edges():
    nodes = [
        {"id": "n1", "name": "变量", "chapter": "第1章"},
        {"id": "n2", "name": "不存在的目录词", "chapter": "第1章"},
        {"id": "n3", "name": "函数", "chapter": "第5章"},
    ]
    edges = [{"from": "n1", "to": "n2"}, {"from": "n1", "to": "n3"}]
    matches = {
        "n1": GroundingMatch(node_id="n1", score=0.81, chunk_id="c1", content_preview="变量定义"),
        "n2": GroundingMatch(node_id="n2", score=0.42, chunk_id="c2", content_preview="目录"),
        "n3": GroundingMatch(node_id="n3", score=0.70, chunk_id="c3", content_preview="函数定义"),
    }

    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
        threshold=0.70,
    )

    assert [node["id"] for node in filtered_nodes] == ["n1", "n3"]
    assert filtered_edges == [{"from": "n1", "to": "n3"}]
    assert metrics["candidate_node_count"] == 3
    assert metrics["kept_node_count"] == 2
    assert metrics["pruned_node_count"] == 1
    assert metrics["body_top1_threshold"] == 0.70
    assert metrics["body_support_pass_ratio"] == 2 / 3
    assert metrics["pruned_nodes"][0]["node_id"] == "n2"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py -q
```

Expected: FAIL because `app.services.kg_body_grounding` does not exist.

- [ ] **Step 3: Implement pure pruning logic**

Create `../backend/app/services/kg_body_grounding.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GroundingMatch:
    node_id: str
    score: float
    chunk_id: str
    content_preview: str


def is_toc_like_chunk(content: str) -> bool:
    text = (content or "").strip()
    lowered = text.lower()
    if not text:
        return True
    toc_markers = ("目录", "contents", "table of contents")
    if any(marker in lowered for marker in toc_markers):
        return True
    short_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(short_lines) >= 4:
        numbered = sum(1 for line in short_lines if line.startswith(("第", "chapter", "Chapter")) or line[:2].isdigit())
        if numbered / len(short_lines) >= 0.6:
            return True
    return False


def filter_supported_knowledge_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    matches: dict[str, GroundingMatch],
    *,
    threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    kept_nodes: list[dict[str, Any]] = []
    pruned_nodes: list[dict[str, Any]] = []
    kept_ids: set[str] = set()

    for node in nodes:
        node_id = str(node.get("id") or "")
        match = matches.get(node_id)
        score = float(match.score) if match else 0.0
        if match and score >= threshold:
            kept_nodes.append(node)
            kept_ids.add(node_id)
        else:
            pruned_nodes.append(
                {
                    "node_id": node_id,
                    "node_name": node.get("name", ""),
                    "chapter": node.get("chapter", ""),
                    "body_top1_score": score,
                    "chunk_id": match.chunk_id if match else "",
                    "content_preview": match.content_preview if match else "",
                }
            )

    kept_edges = [
        edge
        for edge in edges
        if str(edge.get("from") or "") in kept_ids and str(edge.get("to") or "") in kept_ids
    ]
    candidate_count = len(nodes)
    kept_count = len(kept_nodes)
    metrics = {
        "body_top1_threshold": threshold,
        "candidate_node_count": candidate_count,
        "kept_node_count": kept_count,
        "pruned_node_count": len(pruned_nodes),
        "body_support_pass_ratio": kept_count / candidate_count if candidate_count else 0.0,
        "pruned_nodes": pruned_nodes,
    }
    return kept_nodes, kept_edges, metrics
```

- [ ] **Step 4: Add Route A CLI flags**

In `../backend/tools/generate_knowledge_graph.py`, add args:

```python
parser.add_argument("--route-a", action="store_true", help="启用路线A：用正文chunk验证并裁剪目录候选节点")
parser.add_argument("--catalog-id", help="路线A使用的CourseCatalog/Qdrant course_id")
parser.add_argument("--body-score-threshold", type=float, default=0.70, help="正文支撑相似度阈值")
```

Validation:

```python
if args.route_a and not args.catalog_id:
    print("ERROR: --catalog-id is required when --route-a is enabled.", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 5: Wire Route A scoring behind a small adapter**

Add a function in `generate_knowledge_graph.py`:

```python
async def apply_route_a_body_grounding(
    *,
    catalog_id: str,
    nodes: list,
    edges: list,
    threshold: float,
) -> tuple[list, list, dict]:
    from app.services.kg_body_grounding import filter_supported_knowledge_graph

    # Implementation should reuse the existing Qdrant/embedding access path used by the body grounding probe.
    # It must score each node against non-TOC body chunks only, then pass a node_id -> GroundingMatch map
    # to filter_supported_knowledge_graph().
    matches = await build_body_grounding_matches(catalog_id=catalog_id, nodes=nodes)
    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
        threshold=threshold,
    )
    if not filtered_nodes:
        raise ValueError("Route A pruned all nodes; refusing to create an active KG version")
    return filtered_nodes, filtered_edges, metrics
```

Then implement `build_body_grounding_matches(...)` using the same Qdrant collection, embedding provider, TOC exclusion, and score semantics as the existing `/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language.json` probe. Do not introduce mock chunks or SQLite fallback.

- [ ] **Step 6: Save Route A versions with metrics**

In `main_async()` after `validate_and_clean_kg(raw_data)`:

```python
source_type = "outline_llm"
generation_strategy = "legacy_outline"
metrics = {}
if args.route_a:
    nodes, edges, metrics = await apply_route_a_body_grounding(
        catalog_id=args.catalog_id,
        nodes=nodes,
        edges=edges,
        threshold=args.body_score_threshold,
    )
    source_type = "route_a_body_grounded"
    generation_strategy = "route_a_prune_unsupported"
```

Call:

```python
result = await save_knowledge_graph_version(
    course_id,
    nodes,
    edges,
    source_type=source_type,
    generation_strategy=generation_strategy,
    metrics=metrics,
    activate=True,
)
```

- [ ] **Step 7: Run unit tests**

Run:

```bash
../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add app/services/kg_body_grounding.py tools/generate_knowledge_graph.py tests/test_kg_body_grounding.py tests/test_generate_kg.py
git commit -m "增加KG路线A正文支撑裁剪"
```

## Task 5: Real MySQL and Probe Verification

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`
- Use existing probe outputs under `/tmp/kg-resource-probe/`

- [ ] **Step 1: Run backend regression tests with MySQL**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py tests/test_kg_body_grounding.py tests/test_generate_kg.py tests/test_node_resources.py tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Generate a Route A KG version for the C-language sample**

Run from `../backend` with real LLM and Qdrant environment loaded, without printing secrets:

```bash
set -a
. ../agent_service/.env
set +a
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python tools/generate_knowledge_graph.py --course-id 6c698badb60a4809 --catalog-id b2444963f0e54587 --file /tmp/c-lang-toc-outline.txt --route-a --body-score-threshold 0.70 --auto
```

Expected:

- Creates a new `course_knowledge_graphs` version.
- Keeps previous KG version in history.
- Marks the new Route A version active.
- Prints `version`, `graph_id`, `node_count`, `edge_count`, and metrics summary.

- [ ] **Step 3: Verify version history in MySQL**

Run:

```bash
docker exec eduagent-mysql mysql -u root -p123456 duagent -e "SELECT id, course_id, version, is_active, source_type, generation_strategy, JSON_EXTRACT(metrics, '$.body_support_pass_ratio') AS pass_ratio, JSON_EXTRACT(metrics, '$.kept_node_count') AS kept_nodes, JSON_EXTRACT(metrics, '$.pruned_node_count') AS pruned_nodes FROM course_knowledge_graphs WHERE course_id='6c698badb60a4809' AND is_deleted=0 ORDER BY version;"
```

Expected:

- At least two rows for the course.
- Exactly one row has `is_active=1`.
- Active row has `source_type=route_a_body_grounded`.

- [ ] **Step 4: Rerun the KG-to-body chunk grounding probe**

Run the existing body grounding probe command used for the previous report, targeting the active Route A KG and writing:

```text
/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language-route-a.json
/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language-route-a.csv
```

Expected:

- `body_top1_score >= 0.70` pass ratio is `>= 70%`.
- If pass ratio is `< 70%`, mark Route A first version as failed and do not proceed to resource inheritance, ready gate, or audit/sign-off.

- [ ] **Step 5: Verify rollback**

Use `import_knowledge_graph.py` to activate the previous version:

```bash
../.venv/bin/python tools/import_knowledge_graph.py --course-id 6c698badb60a4809 --activate-version 1
```

Then re-activate the Route A version:

```bash
../.venv/bin/python tools/import_knowledge_graph.py --course-id 6c698badb60a4809 --activate-version 2
```

Expected:

- Each activation keeps all KG rows.
- Exactly one active row remains after each command.
- LearningPath active KG lookup follows the active version.

- [ ] **Step 6: Update progress docs**

Append to `WORKFLOW.md`:

```markdown
### 2026-06-10 KG 版本化与路线 A 返工

- 增加 `course_knowledge_graphs` 多版本和 active 版本读取能力。
- `generate_knowledge_graph.py` / `import_knowledge_graph.py` 不再覆盖旧 KG，改为创建版本并支持回滚。
- 路线 A 第一版启用正文 chunk 验证：排除目录型 chunk 后，保留 `body_top1_score >= 0.70` 的节点，裁剪无正文支撑节点和悬空边。
- 固定成功线：新 KG 正文支撑达标率必须从 `21.6%` 提升到 `>=70%`。
- 验证：
  - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_course_knowledge_graph_versions.py tests/test_kg_body_grounding.py tests/test_generate_kg.py tests/test_node_resources.py tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider`
  - Route A 真实生成 task/命令：
  - 正文对账探针输出：
  - 判定：
```

Update `docs/feature-ledger.md` next queue:

```markdown
1. **路线 A 新 KG 正文支撑复验**
   KG 版本 / 回滚基础设施已完成；下一步以 C 语言样本重跑正文支撑探针，确认 `body_top1_score >= 0.70` 节点占比是否达到 `>=70%`。
```

Fill the command, output paths, and final decision with actual values from the run.

- [ ] **Step 7: Commit verification docs**

Run:

```bash
git add WORKFLOW.md docs/feature-ledger.md
git commit -m "归档KG版本化和路线A验证结果"
```

## Do Not Do During This Plan

- Do not add audit/sign-off fields or UI.
- Do not add a KG ready gate.
- Do not change LearningPath frontend behavior.
- Do not make resources inherit KG node names.
- Do not add mock chunks, mock task states, fake resources, or SQLite fallback.
- Do not delete old KG rows during generation.
- Do not print `.env` secrets.

## Final Verification Checklist

- [ ] Existing KG rows are preserved after new generation.
- [ ] Exactly one active KG exists per course.
- [ ] LearningPath refresh reads the active KG.
- [ ] Node resource lookup reads the active KG.
- [ ] Route A creates a new version with metrics.
- [ ] Route A refuses to save an active KG if all nodes are pruned.
- [ ] Body grounding probe pass ratio is `>=70%`, or the implementation is explicitly marked no-go.
- [ ] `WORKFLOW.md` and `docs/feature-ledger.md` record the actual command outputs and decision.
