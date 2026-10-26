# 技术架构与设计方案 (Technical Design)

## 1. 跨层边界与数据流设计

### 1.1 课程资源访问鉴权防线统一 (`backend`)
- **现状问题**：`node_resource_service.py`、`resource_service.py`、`learning_activity_service.py` 均通过 `app.services.resource_scope.ensure_course_resource_access(db, current_user, course_id)` 强制校验课程存在性（404）与师生归属权（403），唯独 `quiz.py::get_questions` 和 `learning_path.py::get_learning_path` 遗漏了该校验。
- **修复方案**：
  - 在 `backend/app/api/v1/quiz.py` 的 `get_questions` 第一行执行 `await ensure_course_resource_access(db, current_user, course_id)`。
  - 在 `backend/app/api/v1/learning_path.py` 的 `get_learning_path` 第一行执行 `await ensure_course_resource_access(db, current_user, course_id)`。
  - **测试兼容性设计**：检查 `backend/tests/test_learning_path_fallback.py`，其中：
    - `test_learning_path_kg_fallback_returns_nodes` 创建了 `CourseOffering(id=course_id, teacher_id=user_id)`，但未向 `courses` 表插入对应的班课 `Course(id=course_id, teacher_id=user_id)`（或 `CourseEnrollment`）。需在该测试的 seed 阶段补齐 `Course(id=course_id, ...)` 与 `CourseEnrollment(course_id=course_id, student_id=user_id)`，使其符合真实业务模型。
    - `test_learning_path_kg_fallback_no_course_offering_returns_empty` 原先请求 `course_id=nonexistent_course` 并断言 200，现应拆分为：对不存在课程断言 404；对已选课但无 KG 的课程断言返回空节点 200。

### 1.2 题库生成 Partial 状态防误删机制 (`backend`)
- **现状问题**：`catalog_quiz_generation_service.py::run_quiz_generation_background` 在汇总所有子任务后，只要 `inserted_question_ids` 非空，就会把整个 `catalog_id`（或 `fanout_course_ids`）下所有不在 `inserted_question_ids` 中的 `baseline` 题目全部软删除（`is_deleted=True`）。当 10 个节点中有 2 个节点超时失败时，这 2 个节点原本完好的历史 baseline 题库被一并抹除。
- **修复方案**：
  1. 在 `generate_quiz_for_child` 成功分支返回的 dict 中增加 `"node_name": node_name`。
  2. 在 `run_quiz_generation_background` 中提取成功节点的名称集合：
     ```python
     completed_node_names = [
         r["node_name"]
         for r in results
         if isinstance(r, dict) and r.get("status") == "completed" and r.get("node_name")
     ]
     ```
  3. 软删除条件收紧：
     - 当 `completed_node_names` 非空时，在 `update(QuizQuestion)` 的 `where` 子句中增加 `QuizQuestion.knowledge_point.in_(completed_node_names)`，确保只替换本次成功重生成的知识点题目，失败节点的存量题目不动。
     - 当 `completed_node_names` 为空但 `inserted_question_ids` 非空（例如单测 Mock 未返回 `node_name`）时，仅在 `failed == 0` 时执行全量替换；若 `failed > 0` 则跳过软删除。

### 1.3 跨服务个性化资源 RAG 检索 `catalog_id` 与业务 `course_id` 解耦 (`backend` ↔ `agent_service_v2`)
- **现状问题**：
  - 教材向量化入库时（`catalog_ingestion_service.py`），写入 Qdrant 的 payload 为 `metadata.course_id = catalog_id`。
  - 个性化资源生成（`personalized_resources.py` 目标驱动生成 & `ai_chat_resource_service.py` 对话内生成）请求 `/agent/v2/personalized-resources/generations` 时，只传了 `course_id = req.course_id`（教学班 ID）。
  - `PersonalizedResourceGenerationRunner._produce_one` 把 `request.course_id` 同时传给了 `writer.write`（内部调 RAG）和 `create_personalized_resource_draft`（内部调 Backend 写库），导致 RAG 拿教学班 ID 去查以 `catalog_id` 建索引的 Qdrant，永远查不到教材原文。
- **修复方案**：
  - **契约扩展（向后兼容）**：在 `PersonalizedResourceGenerationRequest` 中新增 `catalog_id: str | None = None`。
  - **Agent 端职责分离**：在 `PersonalizedResourceGenerationRunner._produce_one` 中：
    - `rag_course_id = (request.catalog_id or request.course_id).strip()`
    - `await writer.write(..., course_id=rag_course_id, ...)` —— 确保 RAG 命中课程目录向量库。
    - 后续草稿创建、校验、审核、发布工具调用依然传入 `course_id=request.course_id` —— 确保数据库记录关联在学生的教学班下。
  - **Backend 端补齐字段**：
    - `backend/app/api/v1/personalized_resources.py`：`res_payload` 中增加 `"catalog_id": catalog_context.catalog_id`。
    - `backend/app/services/ai_chat_resource_service.py`：调用 `/agent/v2/personalized-resources/generations` 的 payload 中增加 `"catalog_id": catalog.catalog_id`。

### 1.4 前端安全退出与非安全上下文 ID 生成 (`frontend`)
- **教师退出登录**：`frontend/src/pages/TeacherConsole.jsx` 解构 `const { user, logout } = useAuth();`，按钮 `onClick` 改为 `() => { logout(); navigate('/'); }`。
- **非安全上下文 `uid()` 工具**：
  - 新建 `frontend/src/utils/id.js`：
    ```javascript
    export function uid() {
      if (typeof globalThis.crypto?.randomUUID === 'function') {
        return globalThis.crypto.randomUUID();
      }
      return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 6)}`;
    }
    ```
  - 替换 `ChatContext.jsx`、`chatStreamEvents.js`、`useRunLogs.js` 中的 `crypto.randomUUID()`。
