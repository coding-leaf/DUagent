# Backend Catalogs Route Modular Refactor Archive

**日期**: 2026-06-18  
**分支**: `refactor/v2-architecture`  
**范围**: `backend/app/api/v1/catalogs.py` 胖路由模块化重构  
**依据**:
- `frontend/AGENTS.md`
- `docs/superpowers/specs/2026-06-18-backend-catalogs-route-refactor-design.md`
- `docs/superpowers/plans/2026-06-18-backend-catalogs-route-modular-refactor-plan.md`

## 目标

将 `backend/app/api/v1/catalogs.py` 从混合路由、DB 查询、状态计算、Agent 调用、后台任务、响应格式化的大文件，拆成清晰的 Route -> Service -> DB 分层结构。

本轮不引入 Repository 层、不引入 Celery/Redis、不修改 Backend <-> Agent 契约、不改变前端 Client API 响应格式。

## 最终结构

- `backend/app/api/v1/catalogs.py`
  - 保留 HTTP 路由、鉴权、请求参数、响应包装、上传文件流式保存等 glue code。
  - 当前约 473 行。
- `backend/app/services/catalog_presenters.py`
  - 响应 DTO / presenter 格式化。
- `backend/app/services/catalog_service.py`
  - Catalog 基础查询、ready catalog 列表。
- `backend/app/services/catalog_material_service.py`
  - Material helper、资料列表、外部资料创建、资料删除、状态重算。
- `backend/app/services/catalog_ingestion_service.py`
  - 资料入库任务启动与模块级后台 runner。
- `backend/app/services/catalog_kg_service.py`
  - KG 状态查询、host course 复用/创建、KG 生成任务启动与模块级后台 runner。
- `backend/app/services/catalog_resource_generation_service.py`
  - Catalog resource 列表聚合、admin 资源软删除、资源生成父子任务创建、Agent 资源生成调用。
- `backend/app/services/catalog_quiz_generation_service.py`
  - Quiz 父子任务创建、后台并发出题、题目落库、父任务聚合。

## 提交清单

- `ea794e7 refactor: 提取课程资源库响应格式化`
- `953af8a refactor: 提取课程资源库基础服务`
- `2453fe7 refactor: 下沉课程资源库资料管理逻辑`
- `467b6c1 refactor: 下沉课程资源库入库任务逻辑`
- `8e8a4d2 refactor: 下沉课程资源库知识图谱任务逻辑`
- `5cacb25 refactor: 下沉课程资源库资源生成逻辑`
- `8658c28 refactor: 下沉课程资源库题库生成逻辑`
- `2fc8e12 docs: 记录 catalogs 模块化重构验收`

## 关键行为保持

- `task_type="course_catalog_ingestion"` 保持不变。
- `task_type="kg_generation"` 保持不变。
- `task_type="resource_generation"` 保持不变。
- `task_type="quiz_generation"` 保持不变。
- Agent 路径保持不变:
  - `/agent/v1/knowledge/ingestions`
  - `/agent/v1/resources/generate`
  - `/agent/v1/assessment/generate-questions`
- KG host course 逻辑保持:
  - 已绑定 teaching class 时优先复用 offering course。
  - 无 offering 时创建 hidden host course。
  - 保留 `with_for_update()` 和 `IntegrityError` 并发兜底。
- Quiz 后台任务保持:
  - `asyncio.gather(..., return_exceptions=True)`
  - semaphore 并发上限 2
  - skeleton fallback 拒绝
  - multi-choice answer 仍格式化为 `A,C`
  - 旧 baseline 题只在新题成功后软删除

## 测试结果

已通过:
- `tests/test_catalog_presenters.py`
- `tests/test_catalog_material_service.py`
- `tests/test_catalog_service.py`
- `tests/test_course_catalogs.py`
- `tests/test_course_catalog_ingestion.py`
- `tests/test_admin_catalog_kg_generation.py`
- `tests/test_admin_catalog_resource_generation.py`
- `tests/test_kg_resource_targets.py`
- 修改文件 `py_compile`

最终 catalogs 回归套件:

```text
74 passed, 1 skipped, 1 failed
```

唯一失败:

```text
tests/test_node_resources.py::test
AssertionError: 1 check(s) FAIL
```

该失败在独立 MySQL 测试库下单跑也复现，且不经过本次拆分出的 catalog service 路径，判断为既有测试/业务不稳定项，已记录在 `WORKFLOW.md`。

## 已知遗留

1. `tests/test_node_resources.py::test` 需要专项排查。
   - 当前表现是综合断言里 1 个 check 失败。
   - 日志显示路径在 learning-path node resources，不是 catalogs route/service 迁移路径。
2. `catalogs.py` 仍保留上传文件流式保存 glue。
   - 这部分涉及 `UploadFile`、storage path、事务和文件清理，后续若继续拆，应单独写小 spec。
3. `tests/test_admin_catalog_resource_generation.py` 同时覆盖 resource webhook、resource generation、quiz generation。
   - 后续可拆成更聚焦的测试文件，降低回归定位成本。

## 下一步建议

### 方案 A: 先修测试基线

优先处理 `tests/test_node_resources.py::test`。

理由:
- 当前最终回归只有这一处失败。
- 若不处理，后续重构容易把既有失败误判为新回归。
- 该测试属于 learning-path node resources，可能暴露真实接口问题或测试夹具污染。

建议步骤:
1. 将 `tests/test_node_resources.py` 拆成具名测试，替代当前单个大 `test()`。
2. 找出失败的具体 check。
3. 明确是业务 bug 还是测试数据问题。
4. 修复后提交独立 commit。

### 方案 B: 继续 backend 胖路由治理

候选目标:
- `backend/app/api/v1/resources.py`
- `backend/app/api/v1/learning_path.py`
- `backend/app/api/v1/profile.py`

建议优先级:
1. 先做和 `test_node_resources.py` 直接相关的 node resources/learning path 路径。
2. 再处理 resource/webhook 聚合逻辑。

### 方案 C: 固化 Backend <-> Agent 边界文档

输出一份 `docs/superpowers/specs/` 或 `docs/` 下的边界说明:
- Backend 调 Agent 的路径、payload、任务表状态流转。
- Agent 不直接连接数据库。
- 所有持久化通过 Backend API / webhook 回写。

这项符合 `frontend/AGENTS.md` 的架构治理方向，可以防止后续 Agent 侧重新引入 DB 直连。

## 推荐下一步

推荐先执行方案 A：修复 `tests/test_node_resources.py::test` 基线。

在它修复前，不建议继续扩大 backend 重构范围；否则最终回归会持续带着红点，降低每次变更的可信度。
