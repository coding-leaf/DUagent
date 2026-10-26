# 实施执行计划 (Implementation Plan)

## 执行清单 (Ordered Checklist)

### Step 1: 后端课程访问权限收口与测试更新 (`backend`)
- [x] 1.1 在 `backend/app/api/v1/quiz.py` 中导入 `ensure_course_resource_access`，并在 `get_questions` 开头调用 `await ensure_course_resource_access(db, current_user, course_id)`。
- [x] 1.2 在 `backend/app/api/v1/learning_path.py` 中导入 `ensure_course_resource_access`，并在 `get_learning_path` 开头调用 `await ensure_course_resource_access(db, current_user, course_id)`。
- [x] 1.3 更新 `backend/tests/test_learning_path_fallback.py`：
  - 为 `test_learning_path_kg_fallback_returns_nodes` 与 `test_quiz_questions_node_id_filter_returns_node_questions` 补齐 `Course` 与 `CourseEnrollment` 选课关系；
  - 更新 `test_learning_path_kg_fallback_no_course_offering_returns_empty`：验证访问不存在课程返回 404，访问未选课课程返回 403，访问已选课但无 Offering/KG 的课程返回 200 空节点。

### Step 2: 后端题库生成 Partial 状态防误删修复 (`backend`)
- [x] 2.1 修改 `backend/app/services/catalog_quiz_generation_service.py`：
  - 在 `generate_quiz_for_child` 成功返回字典中增加 `"node_name": node_name`；
  - 在 `run_quiz_generation_background` 清理旧 baseline 题目时，限定仅清理 `completed_node_names` 对应的知识点（若无 `node_name` 则仅在 `failed == 0` 时清理）。
- [x] 2.2 在 `backend/tests/test_admin_catalog_resource_generation.py` 中新增单元测试，验证当 2 个子节点中 1 个成功、1 个失败（`partial`）时，失败节点已存在的 baseline `QuizQuestion` 不会被软删除（`is_deleted` 保持 `False`）。

### Step 3: 跨服务个性化资源 RAG `catalog_id` 对齐 (`backend` & `agent_service_v2`)
- [x] 3.1 在 `agent_service_v2/src/agent_service_v2/schemas/personalized_resources.py` 的 `PersonalizedResourceGenerationRequest` 中添加 `catalog_id: str | None = None`。
- [x] 3.2 在 `agent_service_v2/src/agent_service_v2/generators/personalized_resource_flow.py` 的 `_produce_one` 中，将传给 `writer.write` 的 `course_id` 设为 `request.catalog_id or request.course_id`，而传给 draft/validate/review/publish 工具的 `course_id` 保持为 `request.course_id`。
- [x] 3.3 在 `backend/app/api/v1/personalized_resources.py` 与 `backend/app/services/ai_chat_resource_service.py` 中向 `/agent/v2/personalized-resources/generations` 传递 `"catalog_id"`。
- [x] 3.4 在 `agent_service_v2/tests/test_personalized_resource_flow.py` 中新增测试，断言当同时提供 `course_id` 与 `catalog_id` 时，`writer.write` 接收到的是 `catalog_id`，而 `create_personalized_resource_draft` 接收到的是 `course_id`。

### Step 4: 前端教师退出登录与 `uid()` 安全回退 (`frontend`)
- [x] 4.1 修改 `frontend/src/pages/TeacherConsole.jsx`，在点击“退出登录”按钮时调用 `logout()` 后再 `navigate('/')`。
- [x] 4.2 新建 `frontend/src/utils/id.js` 实现 `uid()`，并替换 `ChatContext.jsx`、`chatStreamEvents.js`、`useRunLogs.js` 中的 `crypto.randomUUID()`。
- [x] 4.3 在前端单测中补充对 `uid()` 及 `TeacherConsole` 退出登录行为的验证。

---

## 验证门禁 (Validation Gates)

```bash
# 1. 全仓统一门禁（Frontend ESLint + Build, Backend & Agent Ruff, Backend & Agent Pytest）
python check_all.py

# 2. 前端单元测试
cd frontend && npm run test:unit
```
