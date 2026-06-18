# Teaching Service 分层重构设计

## 背景

Phase 2 已进入架构治理与重构阶段，后端 `backend/app/api/v1/` 中仍存在多个胖路由。`catalogs.py` 已完成服务层拆分样板，下一步需要选择低风险、高收益的后端切片继续建立分层范式。

当前 `backend/app/api/v1/teaching.py` 共 438 行，集中承载教师端学生列表、学生信息、单学生学习报告、班级洞察等查询聚合逻辑。该文件没有 Agent 调用、后台任务、SSE、文件系统或环境变量依赖，主要复杂度来自 SQLAlchemy 查询、权限校验和响应 DTO 拼装。因此它适合作为下一阶段后端 Service Layer 重构目标。

本 Spec 以当前运行代码为事实来源，不以历史 OpenAPI 文档推翻现有行为。

## 当前问题

`teaching.py` 当前混合了以下职责：

1. FastAPI route 定义、鉴权依赖、Query 参数约束。
2. 教师对班级的访问校验 `_verify_teacher`。
3. 学生分页列表查询与学生字段拼装。
4. 学生基础信息查询与 404 错误构造。
5. 单学生学习报告聚合：
   - enrollment 校验。
   - evaluation 最新记录查询。
   - profile 知识点掌握/薄弱统计。
   - learning path 节点完成进度。
   - quiz session 统计。
   - mastery breakdown 聚合。
   - weak points 聚合。
   - recent activity 查询。
6. 班级洞察聚合：
   - 班级学生 ID 查询。
   - 平均 quiz 分数与尝试次数。
   - 班级 weak points top 5。
   - learning path 节点状态汇总。

这导致：

- 路由文件承担了本应属于业务查询服务的 DB 聚合逻辑。
- 学生学习报告和班级洞察逻辑无法独立阅读和测试。
- 后续调整教师端报表字段时需要直接修改 route 文件，容易造成接口漂移。
- `profile.py`、`learning_path.py` 等更复杂胖路由尚不适合立即重构，需要一个更小的后端分层样板。

## 架构选型判断

### 选用：分层架构

采用 `Router -> TeachingService -> DB`。

- Router 保留 HTTP 层职责：路径、参数、`Depends`、权限依赖、统一 JSON wrapper。
- `TeachingService` 承接教师端查询业务：班级访问校验、学生列表、学生信息、学习报告、班级洞察。
- DB 访问暂时在 Service 内使用现有 SQLAlchemy `AsyncSession` 完成。

理由：当前痛点是 route 文件过胖、查询聚合散落。Service Layer 能在不改变部署、接口和数据模型的前提下降低认知负担。

### 暂不选用：Repository 模式

第一阶段不新增 `TeachingRepository` 或通用 DAO。

理由：这些查询高度面向教师端报表，依赖 SQLAlchemy 聚合、`case`、`group_by`、`having`、分页和状态过滤。过早拆 Repository 会增加跳转层，不会显著降低复杂度。若后续多个服务复用相同 quiz/learning path 查询，再评估抽 Repository 或 query helper。

### 暂不选用：CQRS / Read Model

不引入读写分离、物化视图或专用 Query Bus。

理由：教师端洞察是读模型倾向的能力，但目前数据量和行为仍可由 SQLAlchemy 查询满足。当前目标是结构治理，不是性能架构重写。

### 暂不选用：策略模式

不把 weak point、mastery、path progress 拆成多个策略类。

理由：当前没有多套可替换算法，只有固定统计规则。拆策略会让简单查询变得碎片化。

### 暂不选用：后台任务 / 事件驱动

不把报表查询改为异步生成任务。

理由：现有接口是同步查询语义，测试也围绕同步返回字段。改成任务会改变 API 行为和前端调用，不属于本次重构。

## 目标

1. 新增 `backend/app/services/teaching_service.py`。
2. 将 `teaching.py` 从 438 行压缩到约 100-140 行。
3. 保持现有 API 路径、参数、响应字段、错误码和 HTTP status 不变。
4. 保持前端调用不变。
5. 增加 service 级测试，让报表聚合逻辑可脱离 route 阅读和验证。
6. 复用现有 API 回归测试，确认无接口漂移。

## 非目标

- 不修改 `profile.py`、`learning_path.py`、`evaluation.py`、`tutoring.py`。
- 不改数据库 schema。
- 不改 Agent Service，不新增 Agent 调用。
- 不修改 `.env`、密钥、volume、上传文件或构建产物。
- 不重写教师端报表算法，只迁移现有行为。
- 不更新已偏移的 `docs/feature-ledger.md`。

## 拆分边界

### 新增 `backend/app/services/teaching_service.py`

建议采用与 `CatalogService` 一致的类风格：

```python
class TeachingService:
    def __init__(self, db: AsyncSession):
        self.db = db
```

公开方法：

- `verify_teacher(class_id: str, current_user: User) -> Course`
- `list_students(class_id: str, current_user: User, page: int, page_size: int) -> dict`
- `get_student_info(class_id: str, student_id: str, current_user: User) -> dict`
- `get_student_learning(class_id: str, student_id: str, current_user: User) -> dict`
- `get_class_insights(class_id: str, current_user: User) -> dict`

私有 helper 可放在同一文件内：

- `_student_list_item(user, enrollment) -> dict`
- `_student_info_item(user) -> dict`
- `_empty_class_insights() -> dict`
- `_knowledge_progress_from_profile(profile) -> dict | None`
- `_path_progress_from_learning_path(path) -> dict | None`
- `_weak_point_item(row) -> dict`
- `_recent_activity_item(session) -> dict`

暂不新增 `teaching_presenters.py`。当前格式化函数数量可控，先放 service 内私有函数，避免过早拆文件。若实现后 service 超过约 350 行或 DTO 函数明显复用，再单独拆 presenter。

### 修改 `backend/app/api/v1/teaching.py`

保留：

- `router = APIRouter(...)`
- route decorators
- `Depends(require_role("teacher", "admin"))`
- `Depends(get_db)`
- `Query` 参数约束
- `{code, message, data}` 标准 wrapper

迁出：

- `_verify_teacher`
- 所有 SQLAlchemy `select` / `func` / `case` 查询
- 响应 DTO 细节拼装
- 报表聚合循环

route 形态示例：

```python
@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    data = await TeachingService(db).get_class_insights(class_id, current_user)
    return {"code": 200, "message": "success", "data": data}
```

## 行为保持清单

必须保持以下现有行为：

1. 课程不存在返回 HTTP 404，detail 为 `{"code": 40400, "message": "课程不存在", "data": None}`。
2. 非任课教师访问返回 HTTP 403，detail 为 `{"code": 40300, "message": "无权访问此班级", "data": None}`。
3. 学生不存在返回 HTTP 404，detail 为 `{"code": 40400, "message": "学生不存在", "data": None}`。
4. 学生未入班返回 HTTP 404，detail 为 `{"code": 40400, "message": "学生未入班", "data": None}`。
5. 学生列表响应字段保持：`students`、`total`、`page`、`page_size`。
6. 单学生学习报告响应字段保持：`student`、`evaluation_summary`、`profile_summary`、`path_progress`、`quiz_stats`、`weak_points`、`recent_activity`。
7. `evaluation_summary.overall_score` 当前固定为 `75.0`，本次不改。
8. `profile_summary.modal_preference` 当前返回 dict keys 的 list，本次不改。
9. `mastery_breakdown` 过滤空知识点，accuracy 为百分比并保留 1 位小数。
10. `weak_points` 和 `weak_points_top` 过滤空知识点，只返回 error_count > 0 的知识点，最多 5 条。
11. `weak_points` 和 `weak_points_top` 按 error_rate 降序、error_count 降序排序。
12. `recent_activity` 最多 5 条，按 `create_time` 倒序。
13. 空班级 insights 返回：
    - `avg_quiz_score: None`
    - `total_quiz_attempts: 0`
    - `weak_points_top: []`
    - `path_node_progress` 四类状态和 `total_nodes` 均为 0。
14. 班级 path progress 只统计 `completed`、`in_progress`、`recommended`、`pending`，忽略未知状态。
15. soft-deleted enrollment、quiz session、quiz answer、quiz question、learning path、evaluation、profile 按现有代码过滤逻辑保持。

## 测试策略

### 新增 service 测试

新增 `backend/tests/test_teaching_service.py`，优先覆盖 service 聚合行为而不是 HTTP wrapper：

1. `verify_teacher`：
   - 课程不存在抛 404。
   - 非任课教师抛 403。
   - 任课教师返回 course。
2. `get_student_learning`：
   - 未入班学生抛 404。
   - weak points 过滤空知识点并只保留错题知识点。
   - mastery breakdown accuracy 计算保持当前语义。
   - recent activity 最多 5 条且倒序。
3. `get_class_insights`：
   - 空班级返回全零结构。
   - quiz 平均分与尝试次数聚合正确。
   - weak points top 过滤空知识点、最多 5 条、排序正确。
   - soft-deleted enrollment 不参与班级聚合。
   - path node progress 忽略未知状态。

### 现有回归测试

实现后运行：

```bash
cd ../backend
../.venv/bin/python -m py_compile app/api/v1/teaching.py app/services/teaching_service.py
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teaching_service_refactor_test.db ../.venv/bin/python -m pytest tests/test_teaching_service.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_student_learning_refactor_test.db ../.venv/bin/python -m pytest tests/test_teacher_student_learning.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/teacher_class_insights_refactor_test.db ../.venv/bin/python -m pytest tests/test_teacher_class_insights.py -q -p no:cacheprovider
TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/api_teaching_refactor_test.db ../.venv/bin/python -m pytest tests/test_api.py -q -p no:cacheprovider
```

如测试暴露现有 fixture 或 SQLite/MySQL 差异，应优先保持现有 API 行为，不借重构机会改变契约。

## 实施步骤

1. 为 `TeachingService` 写 service 级红灯测试，先覆盖 class insights 与 student learning 的关键聚合。
2. 新增 `backend/app/services/teaching_service.py`，把 `_verify_teacher` 和低风险 helper 迁入。
3. 迁移学生列表与学生基础信息查询。
4. 迁移单学生学习报告查询，保持字段和排序不变。
5. 迁移班级洞察查询，保持空班级结构和聚合语义不变。
6. 精简 `backend/app/api/v1/teaching.py`，route 只调用 service 并返回 wrapper。
7. 运行 service 测试、现有 teaching API 回归和语法检查。
8. 更新 `WORKFLOW.md`，记录文件变更、测试结果、接口无漂移。
9. commit 代码与记录。

## 风险与缓解

- **聚合查询迁移时字段漂移**：用现有 `test_teacher_student_learning.py` 和 `test_teacher_class_insights.py` 做 API 回归，同时新增 service 测试锁定核心数据结构。
- **错误 detail 漂移**：service 内继续抛 `HTTPException`，保留现有 detail dict，不引入新异常类型。
- **SQLite/MySQL 聚合差异**：不改变现有 `case`、`func.sum`、`group_by`、`having` 写法，测试继续覆盖 SQLite；若 MySQL 专属失败，单独记录并修复。
- **Service 文件再次变胖**：本次 service 目标是承接教学查询聚合，若实现后接近或超过 350 行，再拆 `teaching_presenters.py` 或 `teaching_query_helpers.py`，不在第一版预拆。
- **权限语义混淆**：`require_role("teacher", "admin")` 保持在 route；`verify_teacher` 继续按当前行为要求 course.teacher_id 等于 current_user.id。因此 admin 角色虽然能通过 role 依赖，但若不是任课教师仍按现有逻辑返回 403。本次不改变该语义。

## 验收标准

1. `backend/app/api/v1/teaching.py` 行数降至约 100-140 行。
2. `backend/app/services/teaching_service.py` 承载教学查询聚合逻辑。
3. 新增 `backend/tests/test_teaching_service.py`，且 service 测试通过。
4. 现有 `test_teacher_student_learning.py`、`test_teacher_class_insights.py`、`test_api.py` teaching 链路通过。
5. 无前端改动，无 API 字段漂移。
6. `WORKFLOW.md` 追加记录，注明接口无漂移。
