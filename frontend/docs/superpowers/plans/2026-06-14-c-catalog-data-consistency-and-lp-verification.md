# C Catalog 数据一致性恢复与 LearningPath 节点资源验证实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复 C 语言 catalog 数据一致性（chunk_count 与 knowledge_status），然后生成/刷新 LearningPath 并跑探针验证节点资源挂载是否正常。

**Architecture:** 纯后端操作。使用已有 repair tool 和 probe 工具，在开发库直接修复 C catalog 数据，然后触发 LearningPath 生成，跑探针验证 `weak_point_tutorials` / `exercises` / `chapter_materials` 三组资源在节点上的命中情况。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, MySQL, Qdrant

**关联符号:**
- C catalog ID: `b2444963f0e54587`
- C 教学班 course ID: `6c698badb60a4809`
- Active KG (version=3, 108 nodes / 100 edges)

---

## Phase 1: C Catalog 数据一致性恢复

### Task 1: 运行 repair tool check 诊断当前状态

**Files:**
- 工具: `../backend/tools/repair_course_catalog_knowledge_status.py`
- Service: `../backend/app/services/course_catalog_knowledge_repair.py`

- [ ] **Step 1: 运行 check 命令诊断 C catalog**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python tools/repair_course_catalog_knowledge_status.py \
  --catalog-id b2444963f0e54587 check
```

- [ ] **Step 2: 解读 check 输出**

关键字段：
- `current_knowledge_status` — 如果为 `ready` 但与 `material_chunk_count` 不匹配，说明历史不一致
- `material_chunk_count` — 当前未删除 material 的 chunk 求和（预期较低或 0）
- `catalog_chunk_count` — catalog 记录的值（预期为历史值 665）
- `reasons` — 如果有 `material_chunks_missing`，说明 catalog 应为 `dirty`
- `repairable` — 如果 `false`，需要 Task 2 的手动修正

- [ ] **Step 3: 查库确认 material 明细**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory, engine
from app.models.catalog import CourseCatalogMaterial
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseCatalogMaterial).where(
                CourseCatalogMaterial.catalog_id == 'b2444963f0e54587',
                CourseCatalogMaterial.is_deleted == False,
            )
        )
        materials = list(result.scalars().all())
        for m in materials:
            print(f'id={m.id} status={m.status} chunk_count={m.chunk_count} filename={m.filename}')
        total = sum(int(m.chunk_count or 0) for m in materials)
        print(f'TOTAL material_chunk_count = {total}')

asyncio.run(main())
await engine.dispose()
"
```

- [ ] **Step 4: 记录诊断结果**

记录 Step 2-3 的实际输出，判断属于哪种修复路径（Task 2 情况 A 或 B），然后 commit。

```bash
git add -A && git commit -m "诊断: C catalog b2444963f0e54587 数据一致性状态记录"
```

### Task 2: 修正 C catalog chunk_count 与 knowledge_status

**情况 A（有 ingested material，但 catalog 数据不一致）：**

如果 Task 1 显示有有效 material（status=ingested 且 chunk_count>0），修正 catalog 级字段。

- [ ] **Step 1: 直接 SQL 修正 catalog chunk_count 与 knowledge_status**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory, engine
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from sqlalchemy import select, func

async def main():
    async with async_session_factory() as db:
        result = await db.execute(
            select(func.coalesce(func.sum(CourseCatalogMaterial.chunk_count), 0))
            .where(
                CourseCatalogMaterial.catalog_id == 'b2444963f0e54587',
                CourseCatalogMaterial.is_deleted == False,
            )
        )
        real_chunks = result.scalar_one()
        print(f'real_chunks = {real_chunks}')

        catalog = await db.get(CourseCatalog, 'b2444963f0e54587')
        if catalog and not catalog.is_deleted:
            catalog.chunk_count = int(real_chunks or 0)
            catalog.knowledge_status = 'ready' if real_chunks > 0 else 'dirty'
            catalog.last_error = None
            await db.commit()
            print(f'UPDATED: chunk_count={catalog.chunk_count} knowledge_status={catalog.knowledge_status}')

asyncio.run(main())
await engine.dispose()
"
```

- [ ] **Step 2: 情况 B（无有效 material，需重新入库）**

如果 `real_chunks = 0` 且无 ingested material，需要：
1. 通过 Admin 前端重新上传一份 C 语言资料到 catalog `b2444963f0e54587`
2. 触发入库向量化 task
3. 等待 task completed
4. 确认 catalog `chunk_count` 和 `knowledge_status` 更新

- [ ] **Step 3: 验证修复**

重跑 Task 1 check 命令，确认：
- `catalog_chunk_count == material_chunk_count`（一致）
- `knowledge_status` 为 `ready`（如果有 chunk）或 `dirty`（若无）

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "修复: C catalog b2444963f0e54587 chunk_count 与 knowledge_status 一致性"
```

---

## Phase 2: LearningPath 生成与节点资源挂载验证

### Task 3: 确认前置条件

- [ ] **Step 1: 验证 C catalog 和 course offering 状态**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory, engine
from app.models.catalog import CourseCatalog, CourseOffering
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, 'b2444963f0e54587')
        if catalog:
            print(f'catalog: status={catalog.status} knowledge_status={catalog.knowledge_status} chunk_count={catalog.chunk_count} kg_host_course_id={catalog.kg_host_course_id}')
        result = await db.execute(
            select(CourseOffering).where(CourseOffering.catalog_id == 'b2444963f0e54587', CourseOffering.is_deleted == False)
        )
        for o in result.scalars().all():
            print(f'offering: id={o.id} course_name={o.course_name}')

asyncio.run(main())
await engine.dispose()
"
```

- [ ] **Step 2: 确认 Agent Service 可达**

```bash
curl -s http://localhost:8002/docs 2>/dev/null | head -5 || echo "Agent Service NOT REACHABLE"
```

如果不可达，需先启动 Agent Service。

- [ ] **Step 3: 确认测试学生已加入 C 课程**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory, engine
from app.models.user import User
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.role == 'student', User.is_deleted == False).limit(5)
        )
        for u in result.scalars().all():
            print(f'student: id={u.id} username={u.username}')

asyncio.run(main())
await engine.dispose()
"
```

选择一个测试学生并确认该生已加入 `6c698badb60a4809` 课程。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "确认: C catalog 修复完成，LearningPath 前置条件就绪"
```

### Task 4: 生成/刷新 LearningPath

- [ ] **Step 1: 获取测试学生的 auth token**

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<TEST_STUDENT_USERNAME>", "password": "<TEST_STUDENT_PASSWORD>"}'
```

从返回的 `data.token` 提取 token。

- [ ] **Step 2: 触发 LearningPath 刷新**

```bash
STUDENT_TOKEN="<TOKEN>"
curl -s -X POST http://localhost:8001/api/v1/learning-path/refresh \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"course_id": "6c698badb60a4809"}'
```

从返回的 `data.task_id` 提取 task_id。

- [ ] **Step 3: 轮询 task 状态**

```bash
TASK_ID="<TASK_ID>"
curl -s http://localhost:8001/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $STUDENT_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['status'])"
```

每隔 5 秒轮询一次直到 status 变为 `completed` 或 `failed`。

- [ ] **Step 4: 处理两种情况**

- **如果 Agent 个性化 LP 生成成功** (`source="learning_path"`)：直接用生成的 LP 做探针验证。
- **如果 Agent LP 不可用**（超时/报错/failed）：不阻塞。`GET /learning-path` 会回退到 KG fallback（`source="kg_fallback"`），探针仍可按 KG fallback 的 108 节点验证资源命中。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "验证: C 课程 6c698badb60a4809 LearningPath 生成/刷新"
```

### Task 5: 运行 LearningPath 节点资源命中探针

- [ ] **Step 1: 执行 LP 资源探针**

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python tools/probe_learning_path_resources.py \
  --catalog-id b2444963f0e54587 \
  --course-id 6c698badb60a4809 \
  --user-id <TEST_STUDENT_ID> \
  --out /tmp/learning-path-resource-probe-c-language-v2.json
```

- [ ] **Step 2: 解读探针结果**

核心指标：
- `learning_path_node_count` — LP 中的节点数（KG fallback 下应为 108）
- `nodes_with_any_resource_count` — 有任意资源的节点数
- `node_resource_coverage_ratio` — `nodes_with_resources / total_nodes`
- `resource_count` / `kg_tagged_resource_count` — 总资源数和 KG 节点标记资源数
- 每个节点的 `weak_point_resource_ids` / `chapter_resource_ids` / `exercise_ids` — 三组资源的实际 ID 列表

判断标准：
- `node_resource_coverage_ratio > 0` → 有节点挂载到资源，前端 `GET /nodes/{node_id}/resources` 可返回数据
- `node_resource_coverage_ratio >= 0.3` → 超过 30% 节点有资源挂载，可接受
- `node_resource_coverage_ratio < 0.3` → 覆盖率低，需诊断 mismatch 原因

- [ ] **Step 3: 如果在覆盖率低，诊断 mismatch**

在探针 JSON 的 `nodes[]` 中检查：
1. `weak_point_resource_ids` 为空 → 资源 `knowledge_point` 字段与节点 `node_name` 不匹配
2. `chapter_resource_ids` 为空 → 资源 `chapter` 字段未设置或 KG 节点未预设 chapter
3. 手动查一对典型的匹配：选一个 empty 节点的 `node_name`，查 Resource 表中是否存在该名称的记录

```bash
cd ../backend && DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/duagent?charset=utf8mb4 \
  ../.venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import async_session_factory, engine
from app.models.others import Resource
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        # 查所有非删除 resource 按 course_id 或 catalog_id
        result = await db.execute(
            select(Resource).where(
                Resource.course_id == '6c698badb60a4809',
                Resource.is_deleted == False,
            ).limit(20)
        )
        for r in result.scalars().all():
            print(f'id={r.id} knowledge_point={r.knowledge_point} chapter={r.chapter} title={r.title} type={r.type}')

asyncio.run(main())
await engine.dispose()
"
```

- [ ] **Step 4: Commit 探针结果**

```bash
git add -A && git commit -m "验证: C 课程 LP 节点资源命中评估完成，覆盖率=<实际数值>"
```

### Task 6: 前端 Node Resources 展示验证（可选，快速冒烟）

如果探针 `node_resource_coverage_ratio > 0`：

- [ ] **Step 1: 启动前端 dev server**

```bash
npm run dev
```

- [ ] **Step 2: 浏览器验证**

以测试学生登录，进入 C 课程 LearningPath 页面，点击节点查看底部面板是否加载 `weak_point_tutorials` / `exercises` / `chapter_materials`。

- [ ] **Step 3: 记录验证结论**

不做新 commit（前端不做代码改动）。

---

## Phase 3: 同步文档

### Task 7: 更新进度文档

**Files:**
- Modify: `docs/feature-ledger.md` — 更新下一步队列
- Modify: `WORKFLOW.md` — 添加验证条目

- [ ] **Step 1: 更新 WORKFLOW.md**

在 `## 最近验证` 下新增 2026-06-14 条目，简要记录：
- C catalog chunk_count / knowledge_status 修复前后的状态
- LP 生成/刷新的方式（Agent 个性化 vs KG fallback）
- 探针覆盖率结果

- [ ] **Step 2: 更新 feature-ledger.md**

更新 `## 当前下一步队列`：
- 第 1 项（C catalog 数据一致性恢复）标记为已完成
- 根据探针结果更新 LearningPath 节点资源验证状态
- 调整队列顺序，下一项为 #28 或 Evaluation refresh

- [ ] **Step 3: Commit**

```bash
git add docs/feature-ledger.md WORKFLOW.md
git commit -m "docs: 更新 C catalog 修复与 LP 资源验证进度"
```

---

## 剩余风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Agent 个性化 LP 不可用 | 中 | 低 — KG fallback 已闭环 | 探针验证仍可跑（用 KG fallback LP） |
| C catalog 无有效 material | 中 | 高 — 阻塞探针 | 重新上传资料入库（Task 2 情况 B） |
| Qdrant 数据缺失 | 低 | 高 — 阻塞 catalog ready | 重新入库 |
| 资源覆盖率低（< 30%） | 中 | 中 — 需额外 KG-Resource 对齐工作 | 探针暴露问题，驱动下一轮设计 |
| 前端节点资源面板不展示 | 低 | 中 — 用户体验缺口 | 快速修复或记录为新的任务项 |

---

## 后续方向（独立计划）

本计划覆盖 Phase 1-2（数据修复 + LP 验证）。Phase 3 的以下任务将另写独立计划：

1. **#28 Admin 用户停用状态契约** — 扩展 `GET /admin/users` 返回 `is_active`/`status` 字段，前后端同步
2. **Evaluation refresh 入口决策** — 决定接前端刷新入口或删除 `refreshEvaluation()` service
3. **AI Chat Hybrid Retrieval 真实闭环** — 在主线许可时跑一次真实闭环验证
